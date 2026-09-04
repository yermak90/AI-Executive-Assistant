import asyncio
import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.db.session import SessionLocal
from app.models.voice_capture import VoiceCapture, VoiceCaptureStatus
from app.services.voice_captures import (
    expire_stale_captures,
    recover_stale_captures,
    run_processing,
    sweep_pending_audio_cleanup,
)

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)


async def _retention_sweep_loop() -> None:
    """PRD §31 P0-3: automatic retention — a periodic in-process sweep, not
    just lazy expiry-on-read. Expires stale captures and retries any audio
    delete that failed on a previous attempt (PRD §31 P1-1)."""
    while True:
        await asyncio.sleep(settings.voice_capture_retention_sweep_seconds)
        db = SessionLocal()
        try:
            await asyncio.to_thread(expire_stale_captures, db)
            await asyncio.to_thread(sweep_pending_audio_cleanup, db)
        except Exception:  # noqa: BLE001 — a transient DB hiccup must not kill the sweep loop permanently
            logger.exception("Voice capture retention sweep failed")
        finally:
            db.close()


async def _claim_next_upload() -> uuid.UUID | None:
    """Returns the id of one UPLOADED capture, if any, without holding the
    session open afterward."""
    db = SessionLocal()
    try:
        capture_id = db.execute(
            select(VoiceCapture.id).where(VoiceCapture.status == VoiceCaptureStatus.UPLOADED).order_by(VoiceCapture.created_at).limit(1)
        ).scalar()
        db.rollback()
        return capture_id
    finally:
        db.close()


async def _voice_processing_worker_loop() -> None:
    """PRD §20/§31 P0-1: 'a DB-backed job record and one in-process worker'
    — literally, a persistent worker task with its own lifecycle, not a
    per-request BackgroundTasks callback. That distinction matters: a
    BackgroundTasks callback is tied to the request that scheduled it and
    can be orphaned mid-flight if that request's async context tears down
    (e.g. a worker recycle, or — observed directly — a test client's
    lifespan shutdown) before the callback finishes, leaking an open DB
    transaction/lock. This worker's lifecycle is the app's own, exactly
    like the retention sweep above, so a capture that's claimed is always
    seen through to a terminal-for-this-attempt state (READY_FOR_REVIEW or
    FAILED) before the app itself stops.

    POST /voice-captures returns 202 as soon as the row exists as UPLOADED
    (see routes/voice_captures.py) and sets `app.state.voice_processing_wake`
    so this loop picks it up immediately rather than waiting for the next
    poll tick; the poll is only the fallback for a wake that fired before
    the loop was listening.
    """
    while True:
        try:
            capture_id = await _claim_next_upload()
            if capture_id is not None:
                db = SessionLocal()
                try:
                    await run_processing(db, capture_id)
                finally:
                    db.rollback()
                    db.close()
                continue  # drain immediately — don't wait for the next wake/poll
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — one bad capture must not kill the worker loop
            logger.exception("Voice capture processing worker iteration failed")

        try:
            await asyncio.wait_for(app.state.voice_processing_wake.wait(), timeout=settings.voice_capture_poll_seconds)
        except asyncio.TimeoutError:
            pass
        app.state.voice_processing_wake.clear()


@app.on_event("startup")
def _recover_stale_voice_captures() -> None:
    """PRD §20: a capture stuck TRANSCRIBING/EXTRACTING when the process died
    must not stay stuck forever — move it to a retriable FAILED on boot."""
    db = SessionLocal()
    try:
        recover_stale_captures(db)
    finally:
        db.close()


@app.on_event("startup")
async def _start_background_tasks() -> None:
    app.state.voice_processing_wake = asyncio.Event()
    app.state.retention_sweep_task = asyncio.create_task(_retention_sweep_loop())
    app.state.voice_processing_task = asyncio.create_task(_voice_processing_worker_loop())


async def _cancel_task(task: "asyncio.Task | None") -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@app.on_event("shutdown")
async def _stop_background_tasks() -> None:
    await _cancel_task(getattr(app.state, "retention_sweep_task", None))
    await _cancel_task(getattr(app.state, "voice_processing_task", None))


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    content: dict[str, str] = {"detail": exc.message}
    if exc.code:
        content["code"] = exc.code
    return JSONResponse(status_code=exc.status_code, content=content)


app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
