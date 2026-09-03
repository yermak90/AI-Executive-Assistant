"""Sprint 2 structured AI contract (PRD §19). STT and extraction are separate
ports; the fake implementations here are deterministic, make no network
calls, and are what CI and local dev run by default (STT_PROVIDER=fake,
LLM_PROVIDER=fake). A real adapter is a separate class implementing the same
Protocol, selected once at the provider-factory seam in voice_captures.py —
nothing else changes.

Transcript text is untrusted data, never instructions (PRD §23 prompt
injection boundary): the fake extractor below only ever copies substrings
into typed candidate fields; it has no notion of "actions" to invoke."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable


class AIProviderError(Exception):
    """Base class for a provider-level failure, carrying a stable error code
    (app.core.error_codes) the caller maps 1:1 onto VoiceCapture.error_code."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class AudioInput:
    data: bytes
    mime_type: str
    duration_ms: int | None


@dataclass(frozen=True)
class TranscriptResult:
    transcript: str
    language_code: str


@runtime_checkable
class TranscriptionProvider(Protocol):
    provider_name: str
    model_name: str | None

    async def transcribe(self, audio: AudioInput, language_hint: str | None) -> TranscriptResult: ...


@dataclass(frozen=True)
class ExtractionContext:
    capture_time: datetime
    timezone: str
    known_people: list[str] = field(default_factory=list)
    known_projects: list[str] = field(default_factory=list)
    language_hint: str | None = None


class DeadlineResolution:
    EXACT = "EXACT"
    INFERRED = "INFERRED"
    AMBIGUOUS = "AMBIGUOUS"
    MISSING = "MISSING"


@dataclass(frozen=True)
class CandidateCheckpointSuggestion:
    client_suggestion_id: str
    title: str
    question: str | None
    reason: str | None
    scheduled_at: datetime
    action_if_at_risk: str | None = None


@dataclass(frozen=True)
class CandidateCommitment:
    title: str
    description: str | None
    direction: str
    owner_name: str | None
    counterparty_name: str | None
    project_name: str | None
    deadline: datetime | None
    deadline_original_text: str | None
    deadline_resolution: str


@dataclass(frozen=True)
class ExtractionResult:
    schema_version: str
    transcript: str
    language_code: str
    candidate: CandidateCommitment
    checkpoint_suggestions: list[CandidateCheckpointSuggestion]
    needs_confirmation: list[str]
    warnings: list[str]


@runtime_checkable
class CommitmentExtractionProvider(Protocol):
    provider_name: str
    model_name: str | None

    async def extract(self, transcript: str, context: ExtractionContext) -> ExtractionResult: ...


# --- Fake providers (deterministic, no network — PRD §20) -------------------


class FakeTranscriptionProvider:
    """The uploaded audio bytes ARE the transcript, UTF-8 encoded. This is a
    test/dev seam, not a claim about real speech: the real adapter (a future,
    separately-configured class implementing the same Protocol) decodes
    actual audio. Kept deterministic so CI needs no network or credentials."""

    provider_name = "fake"
    model_name = "fake-stt-v1"

    async def transcribe(self, audio: AudioInput, language_hint: str | None) -> TranscriptResult:
        try:
            # rstrip a trailing NUL: the WAV container pads an odd-length
            # data chunk with one null byte, which is otherwise valid UTF-8.
            transcript = audio.data.decode("utf-8").rstrip("\x00").strip()
        except UnicodeDecodeError as exc:
            from app.core.error_codes import TRANSCRIPTION_FAILED

            raise AIProviderError(TRANSCRIPTION_FAILED, "Fake STT provider requires UTF-8 audio payload") from exc

        if not transcript:
            from app.core.error_codes import NO_SPEECH_DETECTED

            raise AIProviderError(NO_SPEECH_DETECTED, "No speech detected in the recording")

        return TranscriptResult(transcript=transcript, language_code=language_hint or "ru")


# Weekday names -> Python's Monday=0 index, for "к пятнице" style phrases.
_RU_WEEKDAYS = {
    "понедельник": 0,
    "вторник": 1,
    "среду": 2,
    "среде": 2,
    "среда": 2,
    "четверг": 3,
    "пятницу": 4,
    "пятнице": 4,
    "пятница": 4,
    "субботу": 5,
    "субботе": 5,
    "суббота": 5,
    "воскресенье": 6,
}

_TIME_RE = re.compile(r"\b(\d{1,2})[:.](\d{2})\b")
_EXACT_DATE_RE = re.compile(r"\b(\d{1,2})\s+(сентября|октября|ноября|декабря|января|февраля|марта|апреля|мая|июня|июля|августа)\b")
_MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

_I_OWE_MARKERS = ("я должен", "я должна", "мне нужно", "я обязан")
_INJECTION_MARKERS = ("ignore all instructions", "ignore previous instructions", "delete my tasks", "игнорируй инструкции")

# A very small set of clause-splitting cues so two distinct commitments in
# one utterance ("X должен... В среду нужно...") aren't silently merged.
_CLAUSE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


class FakeCommitmentExtractionProvider:
    """Deterministic rule-based extraction covering PRD §29 Scenarios C–F.
    Not real NLP — a fixture for tests and for exercising the pipeline
    without an LLM. A real LLM-backed adapter implements the same Protocol
    (PRD §19) and is swapped in at the provider-factory seam only."""

    provider_name = "fake"
    model_name = "fake-extractor-v1"

    async def extract(self, transcript: str, context: ExtractionContext) -> ExtractionResult:
        clauses = [c.strip() for c in _CLAUSE_SPLIT_RE.split(transcript) if c.strip()]
        commitment_clauses = [c for c in clauses if self._looks_like_commitment(c)]
        if len(commitment_clauses) > 1:
            from app.core.error_codes import MULTIPLE_COMMITMENTS_DETECTED

            raise AIProviderError(MULTIPLE_COMMITMENTS_DETECTED, "Multiple distinct commitments detected in one recording")

        main_clause = commitment_clauses[0] if commitment_clauses else (clauses[0] if clauses else transcript)

        warnings: list[str] = []
        needs_confirmation: list[str] = []

        direction, owner_name = self._detect_direction_and_owner(main_clause, context.known_people)
        if direction != "I_OWE" and owner_name is None:
            needs_confirmation.append("owner_person_id")

        project_name = self._detect_project(transcript, context.known_projects)

        deadline, deadline_text, resolution = self._resolve_deadline(main_clause, context.capture_time)
        if resolution in (DeadlineResolution.AMBIGUOUS, DeadlineResolution.MISSING):
            needs_confirmation.append("deadline")
        if resolution == DeadlineResolution.AMBIGUOUS:
            warnings.append(f"Не удалось однозначно определить срок: «{deadline_text}»")

        title = self._derive_title(main_clause)

        checkpoint_suggestions: list[CandidateCheckpointSuggestion] = []
        for idx, clause in enumerate(clauses):
            if clause is main_clause or clause == main_clause:
                continue
            cp_deadline, cp_text, cp_resolution = self._resolve_deadline(clause, context.capture_time)
            if cp_resolution not in (DeadlineResolution.EXACT, DeadlineResolution.INFERRED):
                continue
            checkpoint_suggestions.append(
                CandidateCheckpointSuggestion(
                    client_suggestion_id=f"s{idx + 1}",
                    title=self._derive_title(clause),
                    question=None,
                    reason=None,
                    scheduled_at=cp_deadline,
                    action_if_at_risk=None,
                )
            )

        candidate = CandidateCommitment(
            title=title,
            description=None,
            direction=direction,
            owner_name=owner_name,
            counterparty_name=None,
            project_name=project_name,
            deadline=deadline,
            deadline_original_text=deadline_text,
            deadline_resolution=resolution,
        )

        return ExtractionResult(
            schema_version="1.0",
            transcript=transcript,
            language_code=context.language_hint or "ru",
            candidate=candidate,
            checkpoint_suggestions=checkpoint_suggestions,
            needs_confirmation=needs_confirmation,
            warnings=warnings,
        )

    _OWNERSHIP_MARKERS = ("должен", "должна", "обязан")
    _CHECKPOINT_VERBS = ("проверить", "уточнить", "узнать", "убедиться")

    @classmethod
    def _looks_like_commitment(cls, clause: str) -> bool:
        lowered = clause.lower()
        has_ownership = any(marker in lowered for marker in cls._OWNERSHIP_MARKERS)
        if not has_ownership and any(verb in lowered for verb in cls._CHECKPOINT_VERBS):
            # A "нужно проверить..." clause with no ownership marker of its
            # own reads as a managerial check-in on another commitment, not
            # a second independent one (PRD §15.1 primary user story).
            return False
        return has_ownership or any(marker in lowered for marker in ("нужно", "необходимо", "надо"))

    @staticmethod
    def _detect_direction_and_owner(clause: str, known_people: list[str]) -> tuple[str, str | None]:
        lowered = clause.lower()
        if any(marker in lowered for marker in _I_OWE_MARKERS):
            return "I_OWE", None

        for name in known_people:
            if name and name.lower() in lowered:
                return "OWED_TO_ME", name

        # First capitalized Cyrillic word is treated as a plausible
        # (unverified) name — Latin text (e.g. an injection attempt) never
        # becomes a name suggestion.
        match = re.match(r"\s*([А-ЯЁ][а-яё]+)\b", clause)
        if match:
            return "OWED_TO_ME", match.group(1)
        return "OWED_TO_ME", None

    @staticmethod
    def _detect_project(transcript: str, known_projects: list[str]) -> str | None:
        quoted = re.search(r"[«\"]([^»\"]+)[»\"]", transcript)
        if quoted:
            return quoted.group(1)
        lowered = transcript.lower()
        for name in known_projects:
            if name and name.lower() in lowered:
                return name
        return None

    @staticmethod
    def _derive_title(clause: str) -> str:
        cleaned = re.sub(r"^\s*[А-ЯЁA-Z][а-яёa-z]+\s+(должен|должна|обязан)\s+", "", clause)
        cleaned = re.sub(
            r"\s+(к|до|в)\s+(понедельник|вторник|сред[ауе]|четверг|пятниц[ауе]|суббот[ауе]|воскресенье).*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"[.!?]+$", "", cleaned).strip()
        return cleaned[:1].upper() + cleaned[1:] if cleaned else clause.strip()

    @staticmethod
    def _resolve_deadline(clause: str, capture_time: datetime) -> tuple[datetime | None, str | None, str]:
        lowered = clause.lower()

        if "следующей неделе" in lowered or "на след" in lowered:
            return None, "на следующей неделе", DeadlineResolution.AMBIGUOUS

        time_match = _TIME_RE.search(clause)
        hour, minute = (int(time_match.group(1)), int(time_match.group(2))) if time_match else (18, 0)

        exact_match = _EXACT_DATE_RE.search(lowered)
        if exact_match:
            day = int(exact_match.group(1))
            month = _MONTHS_RU[exact_match.group(2)]
            year = capture_time.year
            candidate = capture_time.replace(year=year, month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)
            original = exact_match.group(0) + (f" в {time_match.group(0)}" if time_match else "")
            return candidate, original, DeadlineResolution.EXACT

        for word, weekday in _RU_WEEKDAYS.items():
            if word in lowered:
                days_ahead = (weekday - capture_time.weekday()) % 7
                days_ahead = days_ahead or 7
                candidate = (capture_time + timedelta(days=days_ahead)).replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
                original = f"к {word}" + (f" в {time_match.group(0)}" if time_match else "")
                return candidate, original, DeadlineResolution.INFERRED

        return None, None, DeadlineResolution.MISSING


def get_transcription_provider() -> TranscriptionProvider:
    """Single provider-factory seam (mirrors CheckpointSuggestionProvider in
    Sprint 1). Only this function needs to change to wire in a real adapter;
    no caller depends on which implementation it returns."""
    from app.core.config import settings

    if settings.stt_provider == "fake":
        return FakeTranscriptionProvider()
    raise NotImplementedError(
        f"STT_PROVIDER={settings.stt_provider!r} has no adapter registered yet; only 'fake' ships in this build"
    )


def get_extraction_provider() -> CommitmentExtractionProvider:
    from app.core.config import settings

    if settings.llm_provider == "fake":
        return FakeCommitmentExtractionProvider()
    raise NotImplementedError(
        f"LLM_PROVIDER={settings.llm_provider!r} has no adapter registered yet; only 'fake' ships in this build"
    )
