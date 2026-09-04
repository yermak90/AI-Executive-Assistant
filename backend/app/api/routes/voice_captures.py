import uuid

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.core import error_codes
from app.core.config import settings
from app.core.exceptions import ValidationAppError
from app.db.session import get_db
from app.models.voice_capture import VoiceCaptureStatus
from app.schemas.voice_capture import (
    VoiceCaptureConfirmRequest,
    VoiceCaptureConfirmResponse,
    VoiceCaptureRead,
    VoiceCaptureUploadResponse,
)
from app.services import commitments as commitments_service
from app.services import voice_captures as voice_captures_service

router = APIRouter(prefix="/voice-captures", tags=["voice-captures"])

_UPLOAD_CHUNK_BYTES = 256 * 1024


async def _read_upload_within_limit(file: UploadFile, max_bytes: int) -> bytes:
    """PRD §31 P0-2: enforces the size cap while streaming the upload, so an
    oversized file is rejected as soon as it crosses the limit instead of
    being fully read into memory first."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValidationAppError("Audio exceeds the maximum upload size", code=error_codes.AUDIO_TOO_LARGE)
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("", response_model=VoiceCaptureUploadResponse, status_code=202)
async def create_voice_capture(
    request: Request,
    file: UploadFile = File(...),
    language_hint: str | None = Form(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> VoiceCaptureUploadResponse:
    raw = await _read_upload_within_limit(file, settings.voice_capture_max_bytes)
    capture = await voice_captures_service.create_capture(
        db, raw, file.content_type, file.filename, language_hint, idempotency_key
    )
    # PRD §31 P0-1: return 202 before STT/extraction run. Processing is
    # picked up by the app's own persistent worker loop (main.py), not a
    # per-request background task — that keeps a still-running pipeline
    # safe from being orphaned if this request's own context tears down.
    # Only a freshly created UPLOADED row needs the worker woken — an
    # idempotent replay of an already-processing/-processed capture must
    # not restart it.
    if capture.status == VoiceCaptureStatus.UPLOADED:
        request.app.state.voice_processing_wake.set()
    return VoiceCaptureUploadResponse(id=capture.id, status=capture.status, expires_at=capture.expires_at)


@router.get("", response_model=list[VoiceCaptureRead])
def list_voice_captures(limit: int = Query(default=20, gt=0, le=100), db: Session = Depends(get_db)) -> list[VoiceCaptureRead]:
    captures = voice_captures_service.list_captures(db, limit)
    return [voice_captures_service.to_voice_capture_read(c) for c in captures]


@router.get("/{capture_id}", response_model=VoiceCaptureRead)
def get_voice_capture(capture_id: uuid.UUID, db: Session = Depends(get_db)) -> VoiceCaptureRead:
    capture = voice_captures_service.get_capture_or_raise(db, capture_id)
    return voice_captures_service.to_voice_capture_read(capture)


@router.post("/{capture_id}/retry", response_model=VoiceCaptureRead)
async def retry_voice_capture(capture_id: uuid.UUID, db: Session = Depends(get_db)) -> VoiceCaptureRead:
    capture = await voice_captures_service.retry_capture(db, capture_id)
    return voice_captures_service.to_voice_capture_read(capture)


@router.post("/{capture_id}/confirm", response_model=VoiceCaptureConfirmResponse)
def confirm_voice_capture(
    capture_id: uuid.UUID, data: VoiceCaptureConfirmRequest, db: Session = Depends(get_db)
) -> VoiceCaptureConfirmResponse:
    commitment, capture = voice_captures_service.confirm_capture(db, capture_id, data)
    return VoiceCaptureConfirmResponse(
        commitment=commitments_service.to_commitment_detail(commitment),
        voice_capture=voice_captures_service.to_voice_capture_read(capture),
    )


@router.post("/{capture_id}/discard", response_model=VoiceCaptureRead)
def discard_voice_capture(capture_id: uuid.UUID, db: Session = Depends(get_db)) -> VoiceCaptureRead:
    capture = voice_captures_service.discard_capture(db, capture_id)
    return voice_captures_service.to_voice_capture_read(capture)
