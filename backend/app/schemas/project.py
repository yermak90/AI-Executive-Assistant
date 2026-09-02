import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.validators import reject_explicit_null


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    is_active: bool = True


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None

    _validate_name = field_validator("name")(reject_explicit_null)
    _validate_is_active = field_validator("is_active")(reject_explicit_null)


class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ProjectSummary(BaseModel):
    """Minimal project reference used when embedding into other resources."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class ProjectWithStats(ProjectRead):
    active_commitments_count: int = 0
    overdue_commitments_count: int = 0
