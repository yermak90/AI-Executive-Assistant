"""Strict validation boundary for provider output (PRD §19 / §31 P1-2):
"JSON only; unknown fields rejected. Enum and length constraints are
strict." Every TranscriptionProvider/CommitmentExtractionProvider response —
fake or real — is parsed through these schemas before this service trusts
any of it. A real LLM adapter's raw JSON goes through exactly the same gate
as the fake provider's dataclasses (converted to dict first)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_TEXT_LEN = 10_000
MAX_SHORT_TEXT_LEN = 2_000
MAX_NAME_LEN = 255


class TranscriptSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transcript: str = Field(max_length=MAX_TEXT_LEN)
    language_code: str = Field(min_length=2, max_length=16)


class CandidateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=MAX_TEXT_LEN)
    direction: Literal["OWED_TO_ME", "I_OWE", "TEAM"]
    owner_name: str | None = Field(default=None, max_length=MAX_NAME_LEN)
    counterparty_name: str | None = Field(default=None, max_length=MAX_NAME_LEN)
    project_name: str | None = Field(default=None, max_length=MAX_NAME_LEN)
    deadline: datetime | None = None
    deadline_original_text: str | None = Field(default=None, max_length=255)
    deadline_resolution: Literal["EXACT", "INFERRED", "AMBIGUOUS", "MISSING"]


class CheckpointSuggestionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_suggestion_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=500)
    question: str | None = Field(default=None, max_length=MAX_SHORT_TEXT_LEN)
    reason: str | None = Field(default=None, max_length=MAX_SHORT_TEXT_LEN)
    scheduled_at: datetime
    action_if_at_risk: str | None = Field(default=None, max_length=MAX_SHORT_TEXT_LEN)


class ExtractionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1, max_length=16)
    transcript: str = Field(max_length=MAX_TEXT_LEN)
    language_code: str = Field(min_length=2, max_length=16)
    candidate: CandidateSchema
    checkpoint_suggestions: list[CheckpointSuggestionSchema] = Field(default_factory=list, max_length=20)
    needs_confirmation: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=20)
