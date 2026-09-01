import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.commitment import CommitmentStatus, Direction, SourceType
from app.models.commitment_history import HistoryEventType
from app.schemas.person import PersonSummary
from app.schemas.project import ProjectSummary


class CommitmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    owner_person_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    direction: Direction
    deadline: datetime | None = None


class CommitmentUpdate(BaseModel):
    """General-purpose update. Deadline changes here are still tracked in history."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    owner_person_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    direction: Direction | None = None
    deadline: datetime | None = None


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
    deadline: datetime | None
    is_overdue: bool = False
    person: PersonSummary | None = None
    project: ProjectSummary | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None


class CommitmentDetail(CommitmentRead):
    history: list[CommitmentHistoryRead] = []
