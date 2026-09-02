import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.commitment_checkpoint import CheckpointAssessment, CheckpointSourceType, CheckpointStatus
from app.schemas.validators import reject_explicit_null


class CheckpointCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    question: str | None = None
    reason: str | None = None
    scheduled_at: datetime


class CheckpointUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    question: str | None = None
    reason: str | None = None
    scheduled_at: datetime | None = None

    _validate_title = field_validator("title")(reject_explicit_null)
    _validate_scheduled_at = field_validator("scheduled_at")(reject_explicit_null)


class CheckpointGenerateRequest(BaseModel):
    """Trigger AUTO_RULE checkpoint generation. lead_time_days overrides the
    commitment's stored value for this generation; omit to use the stored
    lead_time_days or fall back to the default planning table (FR-016)."""

    lead_time_days: int | None = Field(default=None, gt=0)


ASSESSABLE_VALUES = (CheckpointAssessment.ON_TRACK, CheckpointAssessment.AT_RISK, CheckpointAssessment.BLOCKED)


class CheckpointAssessRequest(BaseModel):
    assessment: CheckpointAssessment
    assessment_note: str | None = None

    @field_validator("assessment")
    @classmethod
    def must_be_assessable(cls, value: CheckpointAssessment) -> CheckpointAssessment:
        if value not in ASSESSABLE_VALUES:
            raise ValueError("assessment must be one of ON_TRACK, AT_RISK, BLOCKED")
        return value


class CheckpointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    commitment_id: uuid.UUID
    title: str
    question: str | None
    reason: str | None
    scheduled_at: datetime
    status: CheckpointStatus
    assessment: CheckpointAssessment
    source_type: CheckpointSourceType
    action_note: str | None
    assessment_note: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    skipped_at: datetime | None
    assessed_at: datetime | None


class CheckpointGenerateResponse(BaseModel):
    """FR-016: if the rule-computed date already passed (or falls before the
    commitment was created), that signal must not be silently swallowed —
    the caller needs to know an intervention is needed right now, even
    though a checkpoint was still created (in the past) rather than dropped."""

    checkpoints: list[CheckpointRead]
    immediate_attention_required: bool
