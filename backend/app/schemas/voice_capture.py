import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.commitment import Direction
from app.models.voice_capture import VoiceCaptureStatus
from app.schemas.commitment import CommitmentDetail


class CandidateCheckpointRead(BaseModel):
    client_suggestion_id: str
    title: str
    question: str | None = None
    reason: str | None = None
    scheduled_at: datetime
    action_if_at_risk: str | None = None


class CandidateCommitmentRead(BaseModel):
    title: str
    description: str | None = None
    direction: str
    owner_name: str | None = None
    counterparty_name: str | None = None
    project_name: str | None = None
    deadline: datetime | None = None
    deadline_original_text: str | None = None
    deadline_resolution: str


class VoiceCaptureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: VoiceCaptureStatus
    language_code: str | None
    audio_duration_ms: int | None
    transcript_text: str | None
    candidate: CandidateCommitmentRead | None = None
    checkpoint_suggestions: list[CandidateCheckpointRead] = []
    needs_confirmation: list[str] = []
    warnings: list[str]
    error_code: str | None
    error_message: str | None
    processing_attempts: int
    confirmed_commitment_id: uuid.UUID | None
    created_at: datetime
    expires_at: datetime
    processed_at: datetime | None
    confirmed_at: datetime | None


class VoiceCaptureUploadResponse(BaseModel):
    id: uuid.UUID
    status: VoiceCaptureStatus
    expires_at: datetime


class SelectedCheckpointSuggestion(BaseModel):
    client_suggestion_id: str
    title: str = Field(min_length=1, max_length=500)
    question: str | None = None
    reason: str | None = None
    scheduled_at: datetime


class VoiceCaptureConfirmRequest(BaseModel):
    """Final user-selected values (PRD §21.3) — not "accept AI as-is". Deadline
    changes on an *already-confirmed* commitment still go exclusively through
    POST /commitments/{id}/reschedule; this is only the initial value."""

    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    direction: Direction
    owner_person_id: uuid.UUID | None = None
    counterparty_person_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    deadline: datetime | None = None
    source_text: str | None = None
    enable_control: bool = False
    lead_time_days: int | None = Field(default=None, gt=0)
    selected_checkpoint_suggestions: list[SelectedCheckpointSuggestion] = []


class VoiceCaptureConfirmResponse(BaseModel):
    commitment: CommitmentDetail
    voice_capture: VoiceCaptureRead
