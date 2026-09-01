import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


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
        UUID(as_uuid=True), ForeignKey("people.id", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )

    direction: Mapped[Direction] = mapped_column(SqlEnum(Direction, name="commitment_direction"), nullable=False)
    status: Mapped[CommitmentStatus] = mapped_column(
        SqlEnum(CommitmentStatus, name="commitment_status"),
        nullable=False,
        default=CommitmentStatus.ACTIVE,
    )
    source_type: Mapped[SourceType] = mapped_column(
        SqlEnum(SourceType, name="commitment_source_type"),
        nullable=False,
        default=SourceType.MANUAL,
    )

    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner_person: Mapped["Person | None"] = relationship(back_populates="commitments")
    project: Mapped["Project | None"] = relationship(back_populates="commitments")
    history: Mapped[list["CommitmentHistory"]] = relationship(
        back_populates="commitment",
        order_by="CommitmentHistory.created_at",
        cascade="all, delete-orphan",
    )
