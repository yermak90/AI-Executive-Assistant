import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enum_types import portable_enum


class CheckpointStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"


class CheckpointAssessment(str, enum.Enum):
    UNKNOWN = "UNKNOWN"
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    BLOCKED = "BLOCKED"


class CheckpointSourceType(str, enum.Enum):
    MANUAL = "MANUAL"
    AUTO_RULE = "AUTO_RULE"
    # Reserved for Sprint 2 — no LLM generates checkpoints in Sprint 1.
    AI_SUGGESTED = "AI_SUGGESTED"


class CommitmentCheckpoint(Base):
    __tablename__ = "commitment_checkpoints"
    __table_args__ = (
        UniqueConstraint("commitment_id", "scheduled_at", name="uq_commitment_checkpoints_commitment_scheduled_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commitment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    status: Mapped[CheckpointStatus] = mapped_column(
        portable_enum(CheckpointStatus, "checkpoint_status"),
        nullable=False,
        default=CheckpointStatus.PENDING,
        index=True,
    )
    assessment: Mapped[CheckpointAssessment] = mapped_column(
        portable_enum(CheckpointAssessment, "checkpoint_assessment"),
        nullable=False,
        default=CheckpointAssessment.UNKNOWN,
    )
    source_type: Mapped[CheckpointSourceType] = mapped_column(
        portable_enum(CheckpointSourceType, "checkpoint_source_type"),
        nullable=False,
        default=CheckpointSourceType.MANUAL,
    )

    action_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    skipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    commitment: Mapped["Commitment"] = relationship(back_populates="checkpoints")
