import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.validators import reject_explicit_null


class PersonBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    notes: str | None = None


class PersonCreate(PersonBase):
    pass


class PersonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = None

    _validate_name = field_validator("name")(reject_explicit_null)


class PersonRead(PersonBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PersonSummary(BaseModel):
    """Minimal person reference used when embedding into other resources."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class PersonWithStats(PersonRead):
    active_commitments_count: int = 0
