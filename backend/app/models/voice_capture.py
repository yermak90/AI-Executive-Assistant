import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enum_types import portable_enum


class VoiceCaptureStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    TRANSCRIBING = "TRANSCRIBING"
    EXTRACTING = "EXTRACTING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    FAILED = "FAILED"
    CONFIRMED = "CONFIRMED"
    DISCARDED = "DISCARDED"
    EXPIRED = "EXPIRED"


# PRD §18.1 — the only transitions the state machine accepts. Anything else
# (including any transition out of a terminal status) is a 409.
ALLOWED_TRANSITIONS: dict[VoiceCaptureStatus, set[VoiceCaptureStatus]] = {
    VoiceCaptureStatus.UPLOADED: {VoiceCaptureStatus.TRANSCRIBING, VoiceCaptureStatus.DISCARDED, VoiceCaptureStatus.EXPIRED},
    VoiceCaptureStatus.TRANSCRIBING: {
        VoiceCaptureStatus.EXTRACTING,
        VoiceCaptureStatus.FAILED,
        VoiceCaptureStatus.DISCARDED,
        VoiceCaptureStatus.EXPIRED,
    },
    VoiceCaptureStatus.EXTRACTING: {
        VoiceCaptureStatus.READY_FOR_REVIEW,
        VoiceCaptureStatus.FAILED,
        VoiceCaptureStatus.DISCARDED,
        VoiceCaptureStatus.EXPIRED,
    },
    VoiceCaptureStatus.FAILED: {VoiceCaptureStatus.TRANSCRIBING, VoiceCaptureStatus.DISCARDED, VoiceCaptureStatus.EXPIRED},
    VoiceCaptureStatus.READY_FOR_REVIEW: {
        VoiceCaptureStatus.CONFIRMED,
        VoiceCaptureStatus.DISCARDED,
        VoiceCaptureStatus.EXPIRED,
    },
    VoiceCaptureStatus.CONFIRMED: set(),
    VoiceCaptureStatus.DISCARDED: set(),
    VoiceCaptureStatus.EXPIRED: set(),
}


class VoiceCapture(Base):
    __tablename__ = "voice_captures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[VoiceCaptureStatus] = mapped_column(
        portable_enum(VoiceCaptureStatus, "voice_capture_status"),
        nullable=False,
        default=VoiceCaptureStatus.UPLOADED,
        index=True,
    )
    language_code: Mapped[str | None] = mapped_column(String(16), nullable=True)

    audio_storage_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audio_mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    audio_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    audio_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    transcript_text: Mapped[str | None] = mapped_column(String, nullable=True)
    candidate_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    stt_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stt_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    extraction_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extraction_model: Mapped[str | None] = mapped_column(String(128), nullable=True)

    processing_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Idempotency-Key deduplication (PRD §21.1): the same key replays the
    # same capture instead of creating a second one.
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)

    confirmed_commitment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commitments.id", ondelete="SET NULL"), nullable=True, unique=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
