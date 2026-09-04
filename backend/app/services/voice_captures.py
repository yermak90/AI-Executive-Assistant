"""Sprint 2 — Voice Note AI Capture service layer (PRD §§17-25, §31
corrections). Business logic Sprint 1 already owns (direction/ownership,
checkpoint timing, terminal states, history) is never re-implemented here —
see confirm_capture, which reuses commitments_service.create_commitment and
checkpoints_service.create_ai_suggested_checkpoint verbatim (PRD §17.3).

Concurrency model (PRD §31 P0-4): every state transition acquires a
`SELECT ... FOR UPDATE` row lock, re-checks the capture's current status
under that lock, mutates, and commits (which releases the lock) before any
slow I/O (audio decode, provider calls) runs. This makes processing, retry,
discard, expiry, and confirmation safe to call concurrently on the same
capture — a loser of a race simply sees a status that no longer matches
what it expected and backs off instead of double-writing.
"""

from __future__ import annotations

import asyncio
import os
import uuid
import wave
from dataclasses import asdict
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Callable

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
from app.schemas.ai_contract import ExtractionSchema, TranscriptSchema
from app.schemas.commitment import CommitmentCreate
from app.schemas.voice_capture import (
    CandidateCheckpointRead,
    CandidateCommitmentRead,
    VoiceCaptureConfirmRequest,
    VoiceCaptureRead,
)
from app.services import audio_formats
from app.services import checkpoints as checkpoints_service
from app.services import commitments as commitments_service
from app.services.voice_providers import (
    AIProviderError,
    AudioInput,
    ExtractionContext,
    get_extraction_provider,
    get_transcription_provider,
)

ACCEPTED_MIME_TYPES = {"wav": "audio/wav", "mp3": "audio/mpeg", "m4a": "audio/mp4", "aac": "audio/aac"}
_TERMINAL = (VoiceCaptureStatus.CONFIRMED, VoiceCaptureStatus.DISCARDED, VoiceCaptureStatus.EXPIRED)
_TRANSIENT_PROVIDER_CODES = {error_codes.AI_TIMEOUT, error_codes.AI_RATE_LIMITED, error_codes.TRANSCRIPTION_TIMEOUT}


# --- Audio validation (PRD §18.2, §31 P1-4) ---------------------------------


def _sniff_candidates(data: bytes) -> list[str]:
    """Server-side format sniffing — never trusts only the filename or the
    client-declared Content-Type. mp3/aac share an ambiguous 0xFF sync magic
    byte, so both are offered as candidates and validate_audio tries a real
    structural parse of each in order."""
    candidates: list[str] = []
    if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WAVE":
        candidates.append("wav")
    if len(data) >= 8 and data[4:8] == b"ftyp":
        candidates.append("m4a")
    if len(data) >= 3 and data[0:3] == b"ID3":
        candidates.append("mp3")
    elif len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        candidates.extend(["mp3", "aac"])
    return candidates


def validate_audio(raw: bytes, declared_content_type: str | None, filename: str | None) -> tuple[str, int, int | None, bytes]:
    """Returns (mime_type, size_bytes, duration_ms, provider_payload).

    Each accepted format is verified structurally, not just by magic bytes:
    WAV via the stdlib `wave` module, MP3 via a real MPEG frame header parse
    (bitrate/samplerate tables), M4A via an ISO-BMFF moov/mvhd box walk, and
    raw AAC via an ADTS frame walk — real duration + decodability checks for
    every accepted format (PRD §31 P1-4), not just WAV.
    """
    if not raw:
        raise ValidationAppError("Audio upload is empty", code=error_codes.AUDIO_CORRUPT)
    if len(raw) > settings.voice_capture_max_bytes:
        raise ValidationAppError("Audio exceeds the maximum upload size", code=error_codes.AUDIO_TOO_LARGE)

    candidates = _sniff_candidates(raw)
    if not candidates:
        raise ValidationAppError(
            "Unrecognized audio format (accepted: m4a, aac, wav, mp3)", code=error_codes.AUDIO_UNSUPPORTED
        )

    fmt: str | None = None
    duration_ms: int | None = None
    payload = raw
    for candidate in candidates:
        if candidate == "wav":
            try:
                with wave.open(BytesIO(raw), "rb") as wav_file:
                    frames = wav_file.getnframes()
                    rate = wav_file.getframerate()
                    if rate <= 0:
                        continue
                    duration_ms = int(frames / rate * 1000)
                    payload = wav_file.readframes(frames)
                fmt = "wav"
                break
            except (wave.Error, EOFError):
                continue
        elif candidate == "mp3":
            d = audio_formats.mp3_duration_ms(raw)
            if d is not None:
                fmt, duration_ms = "mp3", d
                break
        elif candidate == "m4a":
            d = audio_formats.mp4_duration_ms(raw)
            if d is not None:
                fmt, duration_ms = "m4a", d
                break
        elif candidate == "aac":
            d = audio_formats.adts_aac_duration_ms(raw)
            if d is not None:
                fmt, duration_ms = "aac", d
                break

    if fmt is None:
        raise ValidationAppError("Audio file is corrupt or undecodable", code=error_codes.AUDIO_CORRUPT)

    mime_type = declared_content_type or ACCEPTED_MIME_TYPES[fmt]

    if duration_ms is not None:
        if duration_ms > settings.voice_capture_max_seconds * 1000:
            raise ValidationAppError("Audio exceeds the maximum recording duration", code=error_codes.AUDIO_TOO_LONG)
        if duration_ms < 1000:
            raise ValidationAppError(
                "Recording is too short (minimum 1 second of speech)", code=error_codes.NO_SPEECH_DETECTED
            )

    return mime_type, len(raw), duration_ms, payload


# --- Opaque local storage (PRD §23, §31 P1-1) -------------------------------


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


def _delete_audio_file(key: str) -> bool:
    try:
        _storage_path(key).unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _cleanup_audio_after_commit(db: Session, capture: VoiceCapture) -> None:
    """PRD §31 P1-1: runs only after the state-transition commit has already
    landed, and only clears audio_storage_key once the file is actually
    gone — a failed delete leaves the key in place so
    sweep_pending_audio_cleanup retries it later instead of silently
    orphaning the file forever."""
    key = capture.audio_storage_key
    if not key:
        return
    if _delete_audio_file(key):
        capture.audio_storage_key = None
        db.commit()
        db.refresh(capture)


def sweep_pending_audio_cleanup(db: Session) -> int:
    """Retries deleting audio for any terminal capture whose previous
    cleanup attempt failed (still has a non-null audio_storage_key)."""
    rows = list(
        db.execute(
            select(VoiceCapture).where(
                VoiceCapture.status.in_(_TERMINAL),
                VoiceCapture.audio_storage_key.isnot(None),
            )
        )
        .scalars()
        .all()
    )
    cleaned = 0
    for capture in rows:
        if _delete_audio_file(capture.audio_storage_key):
            capture.audio_storage_key = None
            cleaned += 1
    if cleaned:
        db.commit()
    else:
        db.rollback()
    return cleaned


# --- State machine primitives (PRD §18.1, §31 P0-4) -------------------------


def _transition(capture: VoiceCapture, new_status: VoiceCaptureStatus) -> None:
    allowed = ALLOWED_TRANSITIONS.get(capture.status, set())
    if new_status not in allowed:
        raise ConflictError(f"Cannot transition voice capture from {capture.status.value} to {new_status.value}")
    capture.status = new_status


def _lock_capture(db: Session, capture_id: uuid.UUID) -> VoiceCapture | None:
    return db.execute(select(VoiceCapture).where(VoiceCapture.id == capture_id).with_for_update()).scalar_one_or_none()


def _try_advance(
    db: Session,
    capture_id: uuid.UUID,
    is_expected: Callable[[VoiceCaptureStatus], bool],
    mutate: Callable[[VoiceCapture], None],
) -> VoiceCapture | None:
    """Locks the row, and only if its current status still matches
    `is_expected` applies `mutate` and commits. Otherwise rolls back (a
    concurrent operation already moved the capture elsewhere) and returns
    the capture as-is — the caller treats that as "nothing to do", not an
    error, since it's a race outcome rather than a real failure."""
    capture = _lock_capture(db, capture_id)
    if capture is None:
        db.rollback()
        return None
    if not is_expected(capture.status):
        db.rollback()
        return capture
    mutate(capture)
    db.commit()
    db.refresh(capture)
    return capture


def _maybe_expire_locked(db: Session, capture: VoiceCapture) -> bool:
    """Caller already holds `capture`'s row lock. Expires it in place if
    due, committing (which releases the lock). Returns True if it just
    expired; on False the lock is still held for the caller's own use."""
    if capture.status in _TERMINAL or tz_now() < capture.expires_at:
        return False
    capture.transcript_text = None
    capture.candidate_payload = None
    _transition(capture, VoiceCaptureStatus.EXPIRED)
    db.commit()
    db.refresh(capture)
    _cleanup_audio_after_commit(db, capture)
    return True


def get_capture_or_raise(db: Session, capture_id: uuid.UUID) -> VoiceCapture:
    capture = db.get(VoiceCapture, capture_id)
    if capture is None:
        db.rollback()
        raise NotFoundError(f"Voice capture '{capture_id}' not found")
    if capture.status not in _TERMINAL and tz_now() >= capture.expires_at:
        # Double-checked locking: the common case (not expired) never takes
        # a row lock; only a capture that looks expired pays for one, and
        # re-verifies under it in case something else just handled it.
        locked = _lock_capture(db, capture_id)
        if locked is None:
            db.rollback()
        else:
            expired_now = _maybe_expire_locked(db, locked)
            if not expired_now:
                db.rollback()
            capture = locked
    else:
        # A plain read still opens a transaction under SQLAlchemy's
        # autocommit=False; leaving it open would hold a table-level lock
        # for however long this session lives (which, for a request that
        # also schedules a background task, can outlast the response).
        # Always close it out explicitly rather than relying on a later
        # db.close() to do it.
        db.rollback()
    return capture


def list_captures(db: Session, limit: int = 20) -> list[VoiceCapture]:
    query = select(VoiceCapture).order_by(VoiceCapture.created_at.desc()).limit(limit)
    captures = list(db.execute(query).scalars().all())
    db.rollback()
    return captures


def expire_stale_captures(db: Session) -> int:
    """Periodic retention sweep (PRD §31 P0-3): expires every non-terminal
    capture past its expires_at, independent of anyone reading it. Wired to
    an in-process interval task in main.py's lifespan."""
    ids = [
        row[0]
        for row in db.execute(
            select(VoiceCapture.id).where(VoiceCapture.status.notin_(_TERMINAL), VoiceCapture.expires_at <= tz_now())
        ).all()
    ]
    db.rollback()
    count = 0
    for capture_id in ids:
        capture = _lock_capture(db, capture_id)
        if capture is None:
            db.rollback()
            continue
        if _maybe_expire_locked(db, capture):
            count += 1
        else:
            db.rollback()
    return count


def recover_stale_captures(db: Session) -> int:
    """PRD §20: at startup, in-progress captures interrupted by a crash/
    restart move to a retriable FAILED state instead of being stuck forever.
    Runs before the app accepts traffic, so no row locking is needed here."""
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
    else:
        db.rollback()
    return len(stale)


# --- Upload (PRD §21.1, §31 P0-1/P0-2) --------------------------------------


async def create_capture(
    db: Session,
    raw: bytes,
    content_type: str | None,
    filename: str | None,
    language_hint: str | None,
    idempotency_key: str | None,
) -> VoiceCapture:
    """Validates, stores, and inserts the capture row only — does NOT run
    the STT/extraction pipeline. PRD §31 P0-1: POST /voice-captures must
    return 202 before transcription starts; the caller (route) schedules
    run_processing as a background task once this returns."""
    if idempotency_key:
        existing = db.execute(
            select(VoiceCapture).where(VoiceCapture.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing is not None:
            db.rollback()
            return existing
        db.rollback()

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
        _delete_audio_file(key)
        existing = db.execute(
            select(VoiceCapture).where(VoiceCapture.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        raise
    db.refresh(capture)
    return capture


# --- Processing pipeline (PRD §20, §31 P0-4/P1-2/P1-5/P1-6) -----------------


async def _call_with_retries(
    coro_factory: Callable[[], "asyncio.Future"],
    timeout_seconds: float,
    max_retries: int,
    timeout_code: str,
    timeout_message: str,
) -> object:
    """Wraps one provider call with a configured timeout and a bounded
    number of retries — only for errors classified transient (a timeout, or
    a provider-reported rate limit). Anything else (malformed output,
    business-rule rejections like MULTIPLE_COMMITMENTS_DETECTED) is never
    retried; it propagates immediately."""
    last_error: AIProviderError | None = None
    attempts = max(1, max_retries + 1)
    for attempt in range(attempts):
        try:
            return await asyncio.wait_for(coro_factory(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            last_error = AIProviderError(timeout_code, timeout_message)
        except AIProviderError as exc:
            if exc.code not in _TRANSIENT_PROVIDER_CODES:
                raise
            last_error = exc
        if attempt < attempts - 1:
            await asyncio.sleep(min(0.05 * (2**attempt), 0.5))
    assert last_error is not None
    raise last_error


def _set_failed(capture: VoiceCapture, code: str, message: str) -> None:
    capture.error_code = code
    capture.error_message = message
    _transition(capture, VoiceCaptureStatus.FAILED)


async def run_processing(db: Session, capture_id: uuid.UUID) -> VoiceCapture | None:
    """Runs UPLOADED|FAILED -> TRANSCRIBING -> EXTRACTING ->
    READY_FOR_REVIEW|FAILED for one capture, as a DB-backed job with an
    in-process worker (no Celery/Redis — PRD §20). Every phase transition is
    a short locked read-check-write-commit (PRD §31 P0-4); no lock is held
    during the slow provider I/O in between. Returns None only if the
    capture row no longer exists; otherwise always returns the capture in
    whatever state the pipeline left it (including "unchanged" if a
    concurrent operation raced this one out of its expected starting
    state) — never raises for a normal race, only for a genuine bug."""

    def _start(c: VoiceCapture) -> None:
        c.processing_attempts += 1
        c.processing_started_at = tz_now()
        c.error_code = None
        c.error_message = None
        _transition(c, VoiceCaptureStatus.TRANSCRIBING)

    capture = _try_advance(
        db, capture_id, lambda s: s in (VoiceCaptureStatus.UPLOADED, VoiceCaptureStatus.FAILED), _start
    )
    if capture is None or capture.status != VoiceCaptureStatus.TRANSCRIBING:
        return capture

    # --- Transcription phase (no lock held during I/O) ---------------------
    try:
        raw = _read_audio(capture.audio_storage_key)
    except FileNotFoundError:
        return _try_advance(
            db,
            capture_id,
            lambda s: s == VoiceCaptureStatus.TRANSCRIBING,
            lambda c: _set_failed(c, error_codes.AUDIO_CORRUPT, "Stored audio is no longer available"),
        )

    try:
        _, _, _, payload = validate_audio(raw, capture.audio_mime_type, None)
    except AppError as exc:
        code = exc.code or error_codes.AUDIO_CORRUPT
        return _try_advance(
            db, capture_id, lambda s: s == VoiceCaptureStatus.TRANSCRIBING, lambda c: _set_failed(c, code, exc.message)
        )

    provider = get_transcription_provider()
    try:
        transcript_result = await _call_with_retries(
            lambda: provider.transcribe(
                AudioInput(data=payload, mime_type=capture.audio_mime_type, duration_ms=capture.audio_duration_ms),
                capture.language_code,
            ),
            timeout_seconds=settings.ai_request_timeout_seconds,
            max_retries=settings.ai_max_retries,
            timeout_code=error_codes.TRANSCRIPTION_TIMEOUT,
            timeout_message="STT provider timed out",
        )
        validated_transcript = TranscriptSchema(
            transcript=transcript_result.transcript, language_code=transcript_result.language_code
        )
    except AIProviderError as exc:
        code, message = exc.code, exc.message
        return _try_advance(
            db, capture_id, lambda s: s == VoiceCaptureStatus.TRANSCRIBING, lambda c: _set_failed(c, code, message)
        )
    except PydanticValidationError:
        return _try_advance(
            db,
            capture_id,
            lambda s: s == VoiceCaptureStatus.TRANSCRIBING,
            lambda c: _set_failed(c, error_codes.TRANSCRIPTION_FAILED, "Malformed transcription output"),
        )
    except Exception as exc:  # noqa: BLE001 — PRD §31 P1-5: provider/config errors must never crash the pipeline
        message = f"Unexpected transcription error: {exc}"
        return _try_advance(
            db,
            capture_id,
            lambda s: s == VoiceCaptureStatus.TRANSCRIBING,
            lambda c: _set_failed(c, error_codes.TRANSCRIPTION_FAILED, message),
        )

    def _apply_transcript(c: VoiceCapture) -> None:
        c.transcript_text = validated_transcript.transcript
        c.language_code = validated_transcript.language_code
        c.stt_provider = provider.provider_name
        c.stt_model = provider.model_name
        _transition(c, VoiceCaptureStatus.EXTRACTING)

    capture = _try_advance(db, capture_id, lambda s: s == VoiceCaptureStatus.TRANSCRIBING, _apply_transcript)
    if capture is None or capture.status != VoiceCaptureStatus.EXTRACTING:
        return capture

    # --- Extraction phase ---------------------------------------------------
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

    validated_extraction: ExtractionSchema | None = None
    last_schema_error: Exception | None = None
    for _schema_attempt in range(2):  # PRD §19: one retry ("schema repair") before AI_OUTPUT_INVALID
        try:
            extraction = await _call_with_retries(
                lambda: extractor.extract(capture.transcript_text, context),
                timeout_seconds=settings.ai_request_timeout_seconds,
                max_retries=settings.ai_max_retries,
                timeout_code=error_codes.AI_TIMEOUT,
                timeout_message="Extraction provider timed out",
            )
        except AIProviderError as exc:
            code, message = exc.code, exc.message
            return _try_advance(
                db, capture_id, lambda s: s == VoiceCaptureStatus.EXTRACTING, lambda c: _set_failed(c, code, message)
            )
        except Exception as exc:  # noqa: BLE001 — provider/config/date errors -> a stable failure state, not a crash
            message = f"Unexpected extraction error: {exc}"
            return _try_advance(
                db,
                capture_id,
                lambda s: s == VoiceCaptureStatus.EXTRACTING,
                lambda c: _set_failed(c, error_codes.AI_OUTPUT_INVALID, message),
            )

        try:
            validated_extraction = ExtractionSchema(**asdict(extraction))
            break
        except PydanticValidationError as exc:
            last_schema_error = exc
            continue

    if validated_extraction is None:
        error_detail = f"Provider output failed schema validation: {last_schema_error}"
        return _try_advance(
            db,
            capture_id,
            lambda s: s == VoiceCaptureStatus.EXTRACTING,
            lambda c: _set_failed(c, error_codes.AI_OUTPUT_INVALID, error_detail),
        )

    extraction_result = validated_extraction

    def _apply_extraction(c: VoiceCapture) -> None:
        c.candidate_payload = extraction_result.model_dump(mode="json")
        c.warnings = list(extraction_result.warnings)
        c.extraction_provider = extractor.provider_name
        c.extraction_model = extractor.model_name
        c.processed_at = tz_now()
        _transition(c, VoiceCaptureStatus.READY_FOR_REVIEW)

    return _try_advance(db, capture_id, lambda s: s == VoiceCaptureStatus.EXTRACTING, _apply_extraction)


async def retry_capture(db: Session, capture_id: uuid.UUID) -> VoiceCapture:
    capture = get_capture_or_raise(db, capture_id)
    if capture.status != VoiceCaptureStatus.FAILED:
        raise ConflictError("Retry is only allowed for a FAILED voice capture")
    if capture.processing_attempts >= settings.voice_capture_max_retries:
        raise ConflictError("Retry limit reached for this voice capture", code=error_codes.RETRY_LIMIT_REACHED)
    # run_processing re-locks and re-checks the status itself, so a
    # concurrent retry/processing race just makes one of the two calls a
    # no-op rather than a double-processed capture (PRD §31 P0-4).
    result = await run_processing(db, capture.id)
    if result is None:
        raise NotFoundError(f"Voice capture '{capture_id}' not found")
    return result


def discard_capture(db: Session, capture_id: uuid.UUID) -> VoiceCapture:
    capture = _lock_capture(db, capture_id)
    if capture is None:
        db.rollback()
        raise NotFoundError(f"Voice capture '{capture_id}' not found")
    _maybe_expire_locked(db, capture)

    if capture.status == VoiceCaptureStatus.DISCARDED:
        db.rollback()
        return capture  # PRD §21.3: discard is idempotent.
    if capture.status in (VoiceCaptureStatus.CONFIRMED, VoiceCaptureStatus.EXPIRED):
        db.rollback()
        raise ConflictError(f"Cannot discard a voice capture in status {capture.status.value}")

    capture.transcript_text = None
    capture.candidate_payload = None
    capture.discarded_at = tz_now()
    _transition(capture, VoiceCaptureStatus.DISCARDED)
    db.commit()
    db.refresh(capture)
    _cleanup_audio_after_commit(db, capture)
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
    capture = _lock_capture(db, capture_id)
    if capture is None:
        db.rollback()
        raise NotFoundError(f"Voice capture '{capture_id}' not found")
    _maybe_expire_locked(db, capture)

    if capture.status == VoiceCaptureStatus.CONFIRMED:
        db.rollback()
        commitment = commitments_service.get_commitment_or_raise(db, capture.confirmed_commitment_id)
        return commitment, capture
    if capture.status == VoiceCaptureStatus.EXPIRED:
        db.rollback()
        raise ConflictError("Cannot confirm an expired voice capture", code=error_codes.CAPTURE_EXPIRED)
    if capture.status == VoiceCaptureStatus.DISCARDED:
        db.rollback()
        raise ConflictError("Cannot confirm a discarded voice capture", code=error_codes.CONFIRMATION_INVALID)
    if capture.status != VoiceCaptureStatus.READY_FOR_REVIEW:
        db.rollback()
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
        db.rollback()
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

    # PRD §23/§31 P0-3: a confirmed capture's own transcript/candidate copy
    # is no longer needed — the Commitment already carries the
    # user-approved source_text and a provenance snapshot in its history.
    capture.transcript_text = None
    capture.candidate_payload = None
    capture.confirmed_commitment_id = commitment.id
    capture.confirmed_at = tz_now()
    _transition(capture, VoiceCaptureStatus.CONFIRMED)

    db.commit()
    _cleanup_audio_after_commit(db, capture)
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
