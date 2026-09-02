"""P1-11: Sprint-2 compatibility seam. Only asserts the stub is wired and
free of AI/network calls; a future LLM-backed provider fills the same
Protocol and swaps in via `checkpoints._suggestion_provider`."""

from datetime import timedelta

from app.core.timezone import now as tz_now
from app.models.commitment import Commitment, Direction
from app.services import checkpoints as checkpoints_service
from app.services.checkpoint_suggestions import (
    CheckpointSuggestion,
    CheckpointSuggestionProvider,
    RuleBasedCheckpointSuggestionProvider,
)


def test_rule_based_provider_satisfies_protocol():
    assert isinstance(RuleBasedCheckpointSuggestionProvider(), CheckpointSuggestionProvider)


def test_rule_based_provider_returns_deterministic_suggestion():
    now = tz_now()
    commitment = Commitment(title="Купить материалы", direction=Direction.I_OWE, deadline=now + timedelta(days=5))

    provider = RuleBasedCheckpointSuggestionProvider()
    suggestion = provider.suggest(commitment, now + timedelta(days=3), now)

    assert isinstance(suggestion, CheckpointSuggestion)
    assert "Купить материалы" in suggestion.title
    assert suggestion.question
    assert suggestion.reason


def test_checkpoints_module_uses_the_rule_based_provider_by_default():
    assert isinstance(checkpoints_service._suggestion_provider, RuleBasedCheckpointSuggestionProvider)
