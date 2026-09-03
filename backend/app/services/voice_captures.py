"""Sprint 2 — Voice Note AI Capture service layer (PRD §§17-25).

Business logic Sprint 1 already owns (direction/ownership, checkpoint
timing, terminal states, history) is never re-implemented here — see
confirm_capture, which reuses commitments_service.create_commitment and
checkpoints_service.create_ai_suggested_checkpoint verbatim (PRD §17.3).
"""

from __future__ import annotations

import os
import uuid
import wave
from datetime import timedelta
from io import BytesIO
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import error_codes
from app.core.config import settings
from app.core.exceptions import AppError, ConflictError, NotFoundError, ValidationAppError
from app.core.timezone import now as tz_now
from app.models.commitment import Commitment, SourceType
from app.models.commitment_history import HistoryEventType
from app.models.person import Person
from app.models.project import Project
from app.models.voice_capture import ALLOWED_TRANSITIONS, VoiceCapture, VoiceCaptureStatus
from app.schemas.commitment import CommitmentCreate
from app.schemas.voice_capture import (
    CandidateCheckpointRead,
    CandidateCommitmentRead,
    VoiceCaptureConfirmRequest,
    VoiceCaptureRead,
)
from app.services import checkpoints as checkpoints_service
from app.services import commitments as commitments_service
from app.services.voice_providers import (
    AIProviderError,
    AudioInput,
    ExtractionContext,
    ExtractionResult,
    get_extraction_provider,
    get_transcription_provider,
)

ACCEPTED_MIME_TYPES = {"wav": "audio/wav", "mp3": "audio/mpeg", "m4a": "audio/mp4", "aac": "audio/aac"}


# --- Audio validation (PRD §18.2) -------------------------------------------


def _sniff_format(data: bytes) -> str | None:
    """Server-side format sniffing — never trusts only the filename or the
    client-declared Content-Type (PRD §18.2)."""
    if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return "m4a"
    if len(data) >= 3 and data[0:3] == b"ID3":
        return "mp3"
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return "mp3"
    return None


def validate_audio(raw: bytes, declared_content_type: str | None, filename: str | None) -> tuple[str, int, int | None, bytes]:
    """Returns (mime_type, size_bytes, duration_ms, provider_payload).

    provider_payload is the audio's decoded sample data for formats this MVP
    can parse structurally (WAV, via the stdlib `wave` module); for other
    accepted containers (mp3/m4a/aac) it is the raw file bytes — real
    duration/decodability verification for those formats is deferred to the
    real STT adapter, a documented limitation of this increment.
    """
    if not raw:
        raise ValidationAppError("Audio upload is empty", code=error_codes.AUDIO_CORRUPT)
    if len(raw) > settings.voice_capture_max_bytes:
        raise ValidationAppError("Audio exceeds the maximum upload size", code=error_codes.AUDIO_TOO_LARGE)

    fmt = _sniff_format(raw)
    if fmt is None:
        raise ValidationAppError(
            "Unrecognized audio format (accepted: m4a, aac, wav, mp3)", code=error_codes.AUDIO_UNSUPPORTED
        )

    duration_ms: int | None = None
    payload = raw
    if fmt == "wav":
        try:
            with wave.open(BytesIO(raw), "rb") as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                if rate <= 0:
                    raise ValidationAppError("Audio file is corrupt or undecodable", code=error_codes.AUDIO_CORRUPT)
                duration_ms = int(frames / rate * 1000)
                payload = wav_file.readframes(frames)
        except (wave.Error, EOFError) as exc:
            raise ValidationAppError("Audio file is corrupt or undecodable", code=error_codes.AUDIO_CORRUPT) from exc

    mime_type = declared_content_type or ACCEPTED_MIME_TYPES[fmt]

    if duration_ms is not None:
        if duration_ms > settings.voice_capture_max_seconds * 1000:
            raise ValidationAppError("Audio exceeds the maximum recording duration", code=error_codes.AUDIO_TOO_LONG)
        if duration_ms < 1000:
            raise ValidationAppError(
                "Recording is too short (minimum 1 second of speech)", code=error_codes.NO_SPEECH_DETECTED
            )

    return mime_type, len(raw), duration_ms, payload


# --- Opaque local storage (PRD §23) -----------------------------------------


def _storage_path(key: str) -> Path:
    base = Path(settings.voice_capture_storage_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / key


def store_audio(raw: bytes) -> str:
    # An opaque, server-generated key — never a client-supplied filename —
    # so there is nothing in the key an attacker could use for path traversal.
    key = uuid.uuid4().hex
    path = _storage_path(key)
    path.write_bytes(raw)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def _read_audio(key: str | None) -> bytes:
    if not key:
        raise FileNotFoundError("No audio stored for this capture")
    path = _storage_path(key)
    if not path.exists():
        raise FileNotFoundError(str(path))
    return path.read_bytes()


def delete_audio(key: str | None) -> None:
    if not key:
        return
    try:
        _storage_path(key).unlink(missing_ok=True)
    except OSError:
        pass


# --- State machine (PRD §18.1) ----------------------------------------------


def _transition(capture: VoiceCapture, new_status: VoiceCaptureStatus) -> None:
    allowed = ALLOWED_TRANSITIONS.get(capture.status, set())
    if new_status not in allowed:
        raise ConflictError(f"Cannot transition voice capture from {capture.status.value} to {new_status.value}")
    capture.status = new_status


_TERMINAL = (VoiceCaptureStatus.CONFIRMED, VoiceCaptureStatus.DISCARDED, VoiceCaptureStatus.EXPIRED)


def _expire(db: Session, capture: VoiceCapture, commit: bool = True) -> None:
    delete_audio(capture.audio_storage_key)
    capture.audio_storage_key = None
    capture.transcript_text = None
    capture.candidate_payload = None
    _transition(capture, VoiceCaptureStatus.EXPIRED)
    if commit:
        db.commit()
        db.refresh(capture)


def _lazily_expire(db: Session, capture: VoiceCapture) -> None:
    if capture.status in _TERMINAL:
        return
    if tz_now() >= capture.expires_at:
        _expire(db, capture)


def get_capture_or_raise(db: Session, capture_id: uuid.UUID) -> VoiceCapture:
    capture = db.get(VoiceCapture, capture_id)
    if capture is None:
        raise NotFoundError(f"Voice capture '{capture_id}' not found")
    _lazily_expire(db, capture)
    return capture


def list_captures(db: Session, limit: int = 20) -> list[VoiceCapture]:
    query = select(VoiceCapture).order_by(VoiceCapture.created_at.desc()).limit(limit)
    return list(db.execute(query).scalars().all())


def expire_stale_captures(db: Session) -> int:
    """Sweeps every non-terminal capture past its expires_at (PRD §21.2/§23
    retention). Lazy per-row expiry on read (get_capture_or_raise) already
    covers the common path; this is for an operator-triggered or scheduled
    sweep of captures nobody has read since expiring."""
    now = tz_now()
    stale = list(
        db.execute(
            select(VoiceCapture).where(
                VoiceCapture.status.notin_(_TERMINAL),
                VoiceCapture.expires_at <= now,
            )
        )
        .scalars()
        .all()
    )
    for capture in stale:
        _expire(db, capture, commit=False)
    if stale:
        db.commit()
    return len(stale)


def recover_stale_captures(db: Session) -> int:
    """PRD §20: at startup, in-progress captures interrupted by a crash/
    restart move to a retriable FAILED state instead of being stuck forever."""
    stale = list(
        db.execute(
            select(VoiceCapture).where(
                VoiceCapture.status.in_([VoiceCaptureStatus.TRANSCRIBING, VoiceCaptureStatus.EXTRACTING])
            )
        )
        .scalars()
        .all()
    )
    for capture in stale:
        capture.error_message = "Processing was interrupted by a service restart; please retry"
        capture.error_code = error_codes.TRANSCRIPTION_FAILED
        _transition(capture, VoiceCaptureStatus.FAILED)
    if stale:
        db.commit()
    return len(stale)


# --- Upload and processing (PRD §21.1, §20) ---------------------------------


async def upload_and_process(
    db: Session,
    raw: bytes,
    content_type: str | None,
    filename: str | None,
    language_hint: str | None,
    idempotency_key: str | None,
) -> VoiceCapture:
    if idempotency_key:
        existing = db.execute(
            select(VoiceCapture).where(VoiceCapture.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    mime_type, size, duration_ms, _ = validate_audio(raw, content_type, filename)
    key = store_audio(raw)

    capture = VoiceCapture(
        status=VoiceCaptureStatus.UPLOADED,
        language_code=language_hint,
        audio_storage_key=key,
        audio_mime_type=mime_type,
        audio_size_bytes=size,
        audio_duration_ms=duration_ms,
        warnings=[],
        processing_attempts=0,
        idempotency_key=idempotency_key,
        expires_at=tz_now() + timedelta(hours=settings.voice_capture_ttl_hours),
    )
    db.add(capture)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        delete_audio(key)
        existing = db.execute(
            select(VoiceCapture).where(VoiceCapture.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        raise
    db.refresh(capture)

    return await run_processing(db, capture)


def _fail(db: Session, capture: VoiceCapture, code: str, message: str) -> None:
    capture.error_code = code
    capture.error_message = message
    _transition(capture, VoiceCaptureStatus.FAILED)
    db.commit()
    db.refresh(capture)


def _serialize_extraction(extraction: ExtractionResult) -> dict:
    candidate = extraction.candidate
    return {
        "schema_version": extraction.schema_version,
        "needs_confirmation": extraction.needs_confirmation,
        "candidate": {
            "title": candidate.title,
            "description": candidate.description,
            "direction": candidate.direction,
            "owner_name": candidate.owner_name,
            "counterparty_name": candidate.counterparty_name,
            "project_name": candidate.project_name,
            "deadline": candidate.deadline.isoformat() if candidate.deadline else None,
            "deadline_original_text": candidate.deadline_original_text,
            "deadline_resolution": candidate.deadline_resolution,
        },
        "checkpoint_suggestions": [
            {
                "client_suggestion_id": cp.client_suggestion_id,
                "title": cp.title,
                "question": cp.question,
                "reason": cp.reason,
                "scheduled_at": cp.scheduled_at.isoformat(),
                "action_if_at_risk": cp.action_if_at_risk,
            }
            for cp in extraction.checkpoint_suggestions
        ],
    }


async def run_processing(db: Session, capture: VoiceCapture) -> VoiceCapture:
    """Runs the UPLOADED|FAILED -> TRANSCRIBING -> EXTRACTING ->
    READY_FOR_REVIEW|FAILED pipeline for one capture. A DB-backed job record
    (VoiceCapture.status/processing_attempts) plus this in-process worker are
    what PRD §20 asks for at MVP scale — no Celery/Redis/queue service."""
    if capture.status not in (VoiceCaptureStatus.UPLOADED, VoiceCaptureStatus.FAILED):
        raise ConflictError(f"Cannot process a voice capture in status {capture.status.value}")

    capture.processing_attempts += 1
    capture.processing_started_at = tz_now()
    capture.error_code = None
    capture.error_message = None
    _transition(capture, VoiceCaptureStatus.TRANSCRIBING)
    db.commit()

    try:
        raw = _read_audio(capture.audio_storage_key)
    except FileNotFoundError:
        _fail(db, capture, error_codes.AUDIO_CORRUPT, "Stored audio is no longer available")
        return capture

    try:
        _, _, _, payload = validate_audio(raw, capture.audio_mime_type, None)
    except AppError as exc:
        _fail(db, capture, exc.code or error_codes.AUDIO_CORRUPT, exc.message)
        return capture

    provider = get_transcription_provider()
    try:
        transcript_result = await provider.transcribe(
            AudioInput(data=payload, mime_type=capture.audio_mime_type, duration_ms=capture.audio_duration_ms),
            capture.language_code,
        )
    except AIProviderError as exc:
        _fail(db, capture, exc.code, exc.message)
        return capture

    capture.transcript_text = transcript_result.transcript
    capture.language_code = transcript_result.language_code
    capture.stt_provider = provider.provider_name
    capture.stt_model = provider.model_name
    _transition(capture, VoiceCaptureStatus.EXTRACTING)
    db.commit()

    people = [p.name for p in db.execute(select(Person)).scalars().all()]
    projects = [p.name for p in db.execute(select(Project).where(Project.is_active.is_(True))).scalars().all()]
    context = ExtractionContext(
        capture_time=capture.created_at,
        timezone=settings.app_timezone,
        known_people=people,
        known_projects=projects,
        language_hint=capture.language_code,
    )
    extractor = get_extraction_provider()
    try:
        extraction = await extractor.extract(capture.transcript_text, context)
    except AIProviderError as exc:
        _fail(db, capture, exc.code, exc.message)
        return capture

    capture.candidate_payload = _serialize_extraction(extraction)
    capture.warnings = list(extraction.warnings)
    capture.extraction_provider = extractor.provider_name
    capture.extraction_model = extractor.model_name
    capture.processed_at = tz_now()
    _transition(capture, VoiceCaptureStatus.READY_FOR_REVIEW)
    db.commit()
    db.refresh(capture)
    return capture


async def retry_capture(db: Session, capture_id: uuid.UUID) -> VoiceCapture:
    capture = get_capture_or_raise(db, capture_id)
    if capture.status != VoiceCaptureStatus.FAILED:
        raise ConflictError("Retry is only allowed for a FAILED voice capture")
    if capture.processing_attempts >= settings.voice_capture_max_retries:
        raise ConflictError("Retry limit reached for this voice capture", code=error_codes.RETRY_LIMIT_REACHED)
    return await run_processing(db, capture)


def discard_capture(db: Session, capture_id: uuid.UUID) -> VoiceCapture:
    capture = get_capture_or_raise(db, capture_id)
    if capture.status == VoiceCaptureStatus.DISCARDED:
        return capture  # PRD §21.3: discard is idempotent.
    if capture.status in (VoiceCaptureStatus.CONFIRMED, VoiceCaptureStatus.EXPIRED):
        raise ConflictError(f"Cannot discard a voice capture in status {capture.status.value}")

    delete_audio(capture.audio_storage_key)
    capture.audio_storage_key = None
    capture.transcript_text = None
    capture.candidate_payload = None
    capture.discarded_at = tz_now()
    _transition(capture, VoiceCaptureStatus.DISCARDED)
    db.commit()
    db.refresh(capture)
    return capture


# --- Confirmation (PRD §21.3, §17.3, §17.4) ---------------------------------


def confirm_capture(db: Session, capture_id: uuid.UUID, data: VoiceCaptureConfirmRequest) -> tuple[Commitment, VoiceCapture]:
    """One transaction: locks the capture row, creates the Commitment (Sprint
    1's own create_commitment), creates the selected AI_SUGGESTED checkpoints
    (Sprint 1's own checkpoint validation), links confirmed_commitment_id,
    and marks CONFIRMED. Any failure raises before the single db.commit() —
    nothing partial is left behind. Repeated confirmation of an
    already-CONFIRMED capture is idempotent: it returns the same Commitment,
    never creates a second one (PRD §17.4)."""
    capture = db.execute(
        select(VoiceCapture).where(VoiceCapture.id == capture_id).with_for_update()
    ).scalar_one_or_none()
    if capture is None:
        raise NotFoundError(f"Voice capture '{capture_id}' not found")
    _lazily_expire(db, capture)

    if capture.status == VoiceCaptureStatus.CONFIRMED:
        commitment = commitments_service.get_commitment_or_raise(db, capture.confirmed_commitment_id)
        return commitment, capture
    if capture.status == VoiceCaptureStatus.EXPIRED:
        raise ConflictError("Cannot confirm an expired voice capture", code=error_codes.CAPTURE_EXPIRED)
    if capture.status == VoiceCaptureStatus.DISCARDED:
        raise ConflictError("Cannot confirm a discarded voice capture", code=error_codes.CONFIRMATION_INVALID)
    if capture.status != VoiceCaptureStatus.READY_FOR_REVIEW:
        raise ConflictError(f"Cannot confirm a voice capture in status {capture.status.value}")

    try:
        commitment_create = CommitmentCreate(
            title=data.title,
            description=data.description,
            owner_person_id=data.owner_person_id,
            counterparty_person_id=data.counterparty_person_id,
            project_id=data.project_id,
            direction=data.direction,
            deadline=data.deadline,
            source_text=data.source_text,
            enable_control=data.enable_control,
            lead_time_days=data.lead_time_days,
        )
    except PydanticValidationError as exc:
        raise ValidationAppError(str(exc), code=error_codes.CONFIRMATION_INVALID) from exc

    commitment, _immediate_attention = commitments_service.create_commitment(db, commitment_create, commit=False)
    commitment.source_type = SourceType.VOICE_NOTE

    created_entry = next((h for h in commitment.history if h.event_type == HistoryEventType.CREATED), None)
    if created_entry is not None:
        created_entry.new_value = {
            **(created_entry.new_value or {}),
            "source_type": SourceType.VOICE_NOTE.value,
            "voice_capture_id": str(capture.id),
            "source_text_present": bool(data.source_text),
        }

    for suggestion in data.selected_checkpoint_suggestions:
        checkpoints_service.create_ai_suggested_checkpoint(
            db,
            commitment,
            title=suggestion.title,
            question=suggestion.question,
            reason=suggestion.reason,
            scheduled_at=suggestion.scheduled_at,
            commit=False,
        )

    delete_audio(capture.audio_storage_key)
    capture.audio_storage_key = None
    capture.confirmed_commitment_id = commitment.id
    capture.confirmed_at = tz_now()
    _transition(capture, VoiceCaptureStatus.CONFIRMED)

    db.commit()
    return commitments_service.get_commitment_or_raise(db, commitment.id), capture


# --- Read mapping ------------------------------------------------------------


def to_voice_capture_read(capture: VoiceCapture) -> VoiceCaptureRead:
    candidate: CandidateCommitmentRead | None = None
    checkpoint_suggestions: list[CandidateCheckpointRead] = []
    needs_confirmation: list[str] = []
    if capture.candidate_payload:
        payload = capture.candidate_payload
        if payload.get("candidate"):
            candidate = CandidateCommitmentRead(**payload["candidate"])
        checkpoint_suggestions = [CandidateCheckpointRead(**cp) for cp in payload.get("checkpoint_suggestions", [])]
        needs_confirmation = list(payload.get("needs_confirmation", []))

    return VoiceCaptureRead(
        id=capture.id,
        status=capture.status,
        language_code=capture.language_code,
        audio_duration_ms=capture.audio_duration_ms,
        transcript_text=capture.transcript_text,
        candidate=candidate,
        checkpoint_suggestions=checkpoint_suggestions,
        needs_confirmation=needs_confirmation,
        warnings=list(capture.warnings or []),
        error_code=capture.error_code,
        error_message=capture.error_message,
        processing_attempts=capture.processing_attempts,
        confirmed_commitment_id=capture.confirmed_commitment_id,
        created_at=capture.created_at,
        expires_at=capture.expires_at,
        processed_at=capture.processed_at,
        confirmed_at=capture.confirmed_at,
    )
