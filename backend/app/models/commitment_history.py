import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class HistoryEventType(str, enum.Enum):
    CREATED = "CREATED"
    DEADLINE_CHANGED = "DEADLINE_CHANGED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    UPDATED = "UPDATED"


class CommitmentHistory(Base):
    __tablename__ = "commitment_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commitment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[HistoryEventType] = mapped_column(
        SqlEnum(HistoryEventType, name="commitment_history_event_type"), nullable=False
    )
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    commitment: Mapped["Commitment"] = relationship(back_populates="history")
