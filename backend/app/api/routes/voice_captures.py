import uuid

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.voice_capture import (
    VoiceCaptureConfirmRequest,
    VoiceCaptureConfirmResponse,
    VoiceCaptureRead,
    VoiceCaptureUploadResponse,
)
from app.services import commitments as commitments_service
from app.services import voice_captures as voice_captures_service

router = APIRouter(prefix="/voice-captures", tags=["voice-captures"])


@router.post("", response_model=VoiceCaptureUploadResponse, status_code=202)
async def create_voice_capture(
    file: UploadFile = File(...),
    language_hint: str | None = Form(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> VoiceCaptureUploadResponse:
    raw = await file.read()
    capture = await voice_captures_service.upload_and_process(
        db, raw, file.content_type, file.filename, language_hint, idempotency_key
    )
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
