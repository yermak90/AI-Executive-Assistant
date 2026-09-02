import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enum_types import portable_enum


class Direction(str, enum.Enum):
    OWED_TO_ME = "OWED_TO_ME"
    I_OWE = "I_OWE"
    TEAM = "TEAM"


class CommitmentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class SourceType(str, enum.Enum):
    """Origin of a commitment. Only MANUAL is used in Sprint 1; the rest are
    reserved so Sprint 2 (audio -> STT -> LLM extraction) can reuse this
    column without a schema change."""

    MANUAL = "MANUAL"
    MEETING = "MEETING"
    VOICE_NOTE = "VOICE_NOTE"
    EMAIL = "EMAIL"
    CHAT = "CHAT"


class Commitment(Base):
    __tablename__ = "commitments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.id", ondelete="SET NULL"), nullable=True, index=True
    )
    counterparty_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.id", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )

    direction: Mapped[Direction] = mapped_column(
        portable_enum(Direction, "commitment_direction"), nullable=False, index=True
    )
    status: Mapped[CommitmentStatus] = mapped_column(
        portable_enum(CommitmentStatus, "commitment_status"),
        nullable=False,
        default=CommitmentStatus.ACTIVE,
        index=True,
    )
    source_type: Mapped[SourceType] = mapped_column(
        portable_enum(SourceType, "commitment_source_type"),
        nullable=False,
        default=SourceType.MANUAL,
    )
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner_person: Mapped["Person | None"] = relationship(
        back_populates="owned_commitments", foreign_keys=[owner_person_id]
    )
    counterparty_person: Mapped["Person | None"] = relationship(
        back_populates="counterparty_commitments", foreign_keys=[counterparty_person_id]
    )
    project: Mapped["Project | None"] = relationship(back_populates="commitments")
    history: Mapped[list["CommitmentHistory"]] = relationship(
        back_populates="commitment",
        order_by="CommitmentHistory.created_at",
        cascade="all, delete-orphan",
    )
    checkpoints: Mapped[list["CommitmentCheckpoint"]] = relationship(
        back_populates="commitment",
        order_by="CommitmentCheckpoint.scheduled_at",
        cascade="all, delete-orphan",
    )
