"""Sprint-2 compatibility seam (P1-11).

Defines the interface Sprint 2 will implement with an LLM-backed provider to
draft checkpoint title/question/reason text. Sprint 1 wires in only the
deterministic `RuleBasedCheckpointSuggestionProvider` below — there is no AI
integration anywhere in this module or its caller (`checkpoints.py`).
Swapping providers later must not require changing anything outside this
file plus the one assignment in `checkpoints.py` that picks the active
provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from app.models.commitment import Commitment


@dataclass(frozen=True)
class CheckpointSuggestion:
    title: str
    question: str | None
    reason: str | None


@runtime_checkable
class CheckpointSuggestionProvider(Protocol):
    """Produces the text for one checkpoint scheduled at `scheduled_at` for
    `commitment`. Implementations must be pure and read-only: no DB writes,
    no side effects — the caller owns persistence."""

    def suggest(
        self, commitment: Commitment, scheduled_at: datetime, reference_time: datetime
    ) -> CheckpointSuggestion: ...


class RuleBasedCheckpointSuggestionProvider:
    """Sprint 1's only implementation: a fixed template, no AI involved."""

    def suggest(
        self, commitment: Commitment, scheduled_at: datetime, reference_time: datetime
    ) -> CheckpointSuggestion:
        remaining = commitment.deadline - reference_time if commitment.deadline else None
        remaining_text = _format_remaining(remaining) if remaining else "неизвестно"
        return CheckpointSuggestion(
            title=f"Проверить готовность: {commitment.title}",
            question="Всё ли готово для выполнения обязательства в срок?",
            reason=f"До конечного срока осталось {remaining_text}. Если есть препятствия, необходимо вмешаться сейчас.",
        )


def _format_remaining(remaining: timedelta) -> str:
    total_hours = remaining.total_seconds() / 3600
    if total_hours < 48:
        return f"{max(1, round(total_hours))} ч."
    return f"{max(1, round(total_hours / 24))} дн."
