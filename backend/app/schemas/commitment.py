import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.commitment import CommitmentStatus, Direction, SourceType
from app.models.commitment_history import HistoryEventType
from app.schemas.checkpoint import CheckpointRead
from app.schemas.person import PersonSummary
from app.schemas.project import ProjectSummary
from app.schemas.validators import reject_explicit_null


class Bucket(str, enum.Enum):
    OVERDUE = "overdue"
    TODAY = "today"
    TOMORROW = "tomorrow"
    LATER = "later"
    NO_DEADLINE = "no_deadline"


class ControlHealth(str, enum.Enum):
    ON_TRACK = "ON_TRACK"
    CHECK_DUE = "CHECK_DUE"
    AT_RISK = "AT_RISK"
    BLOCKED = "BLOCKED"


class CommitmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    owner_person_id: uuid.UUID | None = None
    counterparty_person_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    direction: Direction
    deadline: datetime | None = None
    source_text: str | None = None

    # "Настроить контроль" (FR-015): opt-in preliminary control at creation.
    enable_control: bool = False
    lead_time_days: int | None = Field(default=None, gt=0)
    control_question: str | None = None
    control_reason: str | None = None

    @model_validator(mode="after")
    def check_direction_ownership(self) -> "CommitmentCreate":
        if self.direction in (Direction.OWED_TO_ME, Direction.TEAM) and self.owner_person_id is None:
            raise ValueError(f"owner_person_id is required for direction {self.direction.value}")
        if self.direction == Direction.I_OWE and self.owner_person_id is not None:
            raise ValueError("owner_person_id must be omitted for I_OWE (it is implicitly the current user)")
        return self


class CommitmentUpdate(BaseModel):
    """General-purpose update. Deadline changes here are still tracked in history."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    owner_person_id: uuid.UUID | None = None
    counterparty_person_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    direction: Direction | None = None
    deadline: datetime | None = None
    source_text: str | None = None
    lead_time_days: int | None = Field(default=None, gt=0)

    _validate_title = field_validator("title")(reject_explicit_null)
    _validate_direction = field_validator("direction")(reject_explicit_null)


class RescheduleRequest(BaseModel):
    deadline: datetime | None = None


class CommitmentHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: HistoryEventType
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    created_at: datetime


class CommitmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    direction: Direction
    status: CommitmentStatus
    source_type: SourceType
    source_text: str | None
    deadline: datetime | None
    lead_time_days: int | None
    is_overdue: bool = False
    bucket: Bucket | None = None
    control_health: ControlHealth = ControlHealth.ON_TRACK
    person: PersonSummary | None = None
    counterparty: PersonSummary | None = None
    project: ProjectSummary | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None


class CommitmentDetail(CommitmentRead):
    history: list[CommitmentHistoryRead] = []
    checkpoints: list[CheckpointRead] = []


class RescheduleResponse(BaseModel):
    """P1-08: a reschedule can silently strand MANUAL checkpoints past the
    new deadline, or clamp a shifted AUTO_RULE checkpoint to created_at —
    both need to reach the caller instead of disappearing into the plain
    CommitmentDetail response."""

    commitment: CommitmentDetail
    immediate_attention_required: bool
    manual_checkpoints_after_deadline: list[CheckpointRead]
