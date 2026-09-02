import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enum_types import portable_enum


class HistoryEventType(str, enum.Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    DEADLINE_CHANGED = "DEADLINE_CHANGED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    CHECKPOINT_CREATED = "CHECKPOINT_CREATED"
    CHECKPOINT_UPDATED = "CHECKPOINT_UPDATED"
    CHECKPOINT_RESCHEDULED = "CHECKPOINT_RESCHEDULED"
    CHECKPOINT_COMPLETED = "CHECKPOINT_COMPLETED"
    CHECKPOINT_SKIPPED = "CHECKPOINT_SKIPPED"
    CHECKPOINT_ASSESSED_ON_TRACK = "CHECKPOINT_ASSESSED_ON_TRACK"
    CHECKPOINT_ASSESSED_AT_RISK = "CHECKPOINT_ASSESSED_AT_RISK"
    CHECKPOINT_ASSESSED_BLOCKED = "CHECKPOINT_ASSESSED_BLOCKED"
    CHECKPOINT_AUTO_RECALCULATED = "CHECKPOINT_AUTO_RECALCULATED"


class CommitmentHistory(Base):
    __tablename__ = "commitment_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commitment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[HistoryEventType] = mapped_column(
        portable_enum(HistoryEventType, "commitment_history_event_type", length=40), nullable=False
    )
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    commitment: Mapped["Commitment"] = relationship(back_populates="history")
