from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.db.session import SessionLocal
from app.services.voice_captures import recover_stale_captures

app = FastAPI(title=settings.app_name)


@app.on_event("startup")
def _recover_stale_voice_captures() -> None:
    """PRD §20: a capture stuck TRANSCRIBING/EXTRACTING when the process died
    must not stay stuck forever — move it to a retriable FAILED on boot."""
    db = SessionLocal()
    try:
        recover_stale_captures(db)
    finally:
        db.close()

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
