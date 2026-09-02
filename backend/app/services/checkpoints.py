import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.timezone import now as tz_now
from app.models.commitment import Commitment, CommitmentStatus
from app.models.commitment_checkpoint import (
    CheckpointAssessment,
    CheckpointSourceType,
    CheckpointStatus,
    CommitmentCheckpoint,
)
from app.models.commitment_history import CommitmentHistory, HistoryEventType
from app.schemas.checkpoint import CheckpointAssessRequest, CheckpointCreate, CheckpointUpdate
from app.schemas.commitment import ControlHealth
from app.services.checkpoint_suggestions import CheckpointSuggestionProvider, RuleBasedCheckpointSuggestionProvider

REASON_COMPLETED = "Обязательство выполнено"
REASON_CANCELLED = "Обязательство отменено"

# P1-11 / Sprint-2 compatibility: the only place that picks which
# CheckpointSuggestionProvider drafts auto-generated checkpoint text. Sprint
# 1 always uses the rule-based provider; a future LLM-backed provider would
# be swapped in here without touching generate_auto_checkpoints itself.
_suggestion_provider: CheckpointSuggestionProvider = RuleBasedCheckpointSuggestionProvider()

_ASSESSMENT_EVENT: dict[CheckpointAssessment, HistoryEventType] = {
    CheckpointAssessment.ON_TRACK: HistoryEventType.CHECKPOINT_ASSESSED_ON_TRACK,
    CheckpointAssessment.AT_RISK: HistoryEventType.CHECKPOINT_ASSESSED_AT_RISK,
    CheckpointAssessment.BLOCKED: HistoryEventType.CHECKPOINT_ASSESSED_BLOCKED,
}


def _checkpoint_snapshot(cp: CommitmentCheckpoint) -> dict:
    return {
        "title": cp.title,
        "scheduled_at": cp.scheduled_at.isoformat(),
        "status": cp.status.value,
    }


def _add_history(db: Session, commitment_id: uuid.UUID, event_type: HistoryEventType, old, new) -> None:
    db.add(CommitmentHistory(commitment_id=commitment_id, event_type=event_type, old_value=old, new_value=new))


def get_checkpoint_or_raise(db: Session, checkpoint_id: uuid.UUID) -> CommitmentCheckpoint:
    checkpoint = db.get(CommitmentCheckpoint, checkpoint_id)
    if checkpoint is None:
        raise NotFoundError(f"Checkpoint '{checkpoint_id}' not found")
    return checkpoint


def list_checkpoints(db: Session, commitment_id: uuid.UUID) -> list[CommitmentCheckpoint]:
    query = (
        select(CommitmentCheckpoint)
        .where(CommitmentCheckpoint.commitment_id == commitment_id)
        .order_by(CommitmentCheckpoint.scheduled_at)
    )
    return list(db.execute(query).scalars().all())


def _validate_checkpoint_timing(commitment: Commitment, scheduled_at: datetime) -> None:
    if commitment.status != CommitmentStatus.ACTIVE:
        raise ConflictError("Cannot schedule a checkpoint for a commitment that is not ACTIVE")
    if scheduled_at < commitment.created_at:
        raise ValidationAppError("Checkpoint cannot be scheduled before the commitment was created")
    if commitment.deadline is not None and scheduled_at >= commitment.deadline:
        raise ValidationAppError("Checkpoint must be scheduled before the commitment's deadline")


def _has_duplicate(commitment: Commitment, scheduled_at: datetime, exclude_id: uuid.UUID | None = None) -> bool:
    return any(
        cp.scheduled_at == scheduled_at and cp.id != exclude_id
        for cp in commitment.checkpoints
    )


def create_manual_checkpoint(db: Session, commitment: Commitment, data: CheckpointCreate) -> CommitmentCheckpoint:
    _validate_checkpoint_timing(commitment, data.scheduled_at)
    if _has_duplicate(commitment, data.scheduled_at):
        raise ValidationAppError("A checkpoint is already scheduled at this exact time")

    checkpoint = CommitmentCheckpoint(
        commitment_id=commitment.id,
        title=data.title,
        question=data.question,
        reason=data.reason,
        scheduled_at=data.scheduled_at,
        source_type=CheckpointSourceType.MANUAL,
    )
    db.add(checkpoint)
    db.flush()
    _add_history(db, commitment.id, HistoryEventType.CHECKPOINT_CREATED, None, _checkpoint_snapshot(checkpoint))
    db.commit()
    db.refresh(checkpoint)
    return checkpoint


def update_checkpoint(db: Session, checkpoint: CommitmentCheckpoint, data: CheckpointUpdate) -> CommitmentCheckpoint:
    if checkpoint.status != CheckpointStatus.PENDING:
        raise ConflictError("Only a PENDING checkpoint can be edited")

    commitment = checkpoint.commitment
    updates = data.model_dump(exclude_unset=True)

    if "scheduled_at" in updates:
        new_scheduled_at = updates.pop("scheduled_at")
        _validate_checkpoint_timing(commitment, new_scheduled_at)
        if new_scheduled_at != checkpoint.scheduled_at:
            if _has_duplicate(commitment, new_scheduled_at, exclude_id=checkpoint.id):
                raise ValidationAppError("A checkpoint is already scheduled at this exact time")
            old_scheduled_at = checkpoint.scheduled_at
            checkpoint.scheduled_at = new_scheduled_at
            _add_history(
                db,
                commitment.id,
                HistoryEventType.CHECKPOINT_RESCHEDULED,
                {"scheduled_at": old_scheduled_at.isoformat(), "title": checkpoint.title},
                {"scheduled_at": new_scheduled_at.isoformat(), "title": checkpoint.title},
            )

    changed_old: dict[str, object] = {}
    changed_new: dict[str, object] = {}
    for field in ("title", "question", "reason"):
        if field not in updates:
            continue
        new_value = updates[field]
        old_value = getattr(checkpoint, field)
        if new_value == old_value:
            continue
        changed_old[field] = old_value
        changed_new[field] = new_value
        setattr(checkpoint, field, new_value)

    if changed_new:
        _add_history(db, commitment.id, HistoryEventType.CHECKPOINT_UPDATED, changed_old, changed_new)

    db.commit()
    db.refresh(checkpoint)
    return checkpoint


def delete_checkpoint(db: Session, checkpoint: CommitmentCheckpoint) -> None:
    if checkpoint.status != CheckpointStatus.PENDING:
        raise ConflictError("Only a PENDING checkpoint can be deleted")
    db.delete(checkpoint)
    db.commit()


def skip_checkpoint(db: Session, checkpoint: CommitmentCheckpoint, reason: str | None = None) -> CommitmentCheckpoint:
    if checkpoint.status != CheckpointStatus.PENDING:
        raise ConflictError("Only a PENDING checkpoint can be skipped")

    now = tz_now()
    checkpoint.status = CheckpointStatus.SKIPPED
    checkpoint.skipped_at = now
    if reason:
        checkpoint.action_note = reason

    _add_history(
        db,
        checkpoint.commitment_id,
        HistoryEventType.CHECKPOINT_SKIPPED,
        None,
        {"title": checkpoint.title, "reason": reason},
    )
    db.commit()
    db.refresh(checkpoint)
    return checkpoint


def skip_pending_checkpoints(db: Session, commitment: Commitment, reason: str, now: datetime) -> None:
    """Used when a commitment is completed/cancelled: all still-pending
    checkpoints are closed out as SKIPPED rather than left dangling."""
    for checkpoint in commitment.checkpoints:
        if checkpoint.status != CheckpointStatus.PENDING:
            continue
        checkpoint.status = CheckpointStatus.SKIPPED
        checkpoint.skipped_at = now
        checkpoint.action_note = reason
        _add_history(
            db,
            commitment.id,
            HistoryEventType.CHECKPOINT_SKIPPED,
            None,
            {"title": checkpoint.title, "reason": reason},
        )


def assess_checkpoint(
    db: Session, checkpoint: CommitmentCheckpoint, data: CheckpointAssessRequest
) -> CommitmentCheckpoint:
    if checkpoint.status != CheckpointStatus.PENDING:
        raise ConflictError("Only a PENDING checkpoint can be assessed")

    now = tz_now()
    checkpoint.assessment = data.assessment
    checkpoint.assessment_note = data.assessment_note
    checkpoint.status = CheckpointStatus.COMPLETED
    checkpoint.assessed_at = now
    checkpoint.completed_at = now

    _add_history(
        db,
        checkpoint.commitment_id,
        _ASSESSMENT_EVENT[data.assessment],
        None,
        {"title": checkpoint.title, "assessment_note": data.assessment_note},
    )
    db.commit()
    db.refresh(checkpoint)
    return checkpoint


# --- Rule-based generation (FR-015 / FR-016 / FR-017) -----------------------


def _default_rule_schedule(deadline: datetime, reference_time: datetime, created_at: datetime) -> list[datetime]:
    remaining = deadline - reference_time
    if remaining <= timedelta(hours=24):
        return [deadline - timedelta(hours=2)]
    if remaining <= timedelta(days=3):
        return [deadline - timedelta(days=1)]
    if remaining <= timedelta(days=7):
        return [deadline - timedelta(days=2)]
    if remaining <= timedelta(days=14):
        return [deadline - timedelta(days=3)]

    midpoint = created_at + (deadline - created_at) / 2
    return [midpoint, deadline - timedelta(days=3)]


def generate_auto_checkpoints(
    db: Session,
    commitment: Commitment,
    lead_time_days: int | None,
    reference_time: datetime,
    question_override: str | None = None,
    reason_override: str | None = None,
    commit: bool = True,
) -> tuple[list[CommitmentCheckpoint], bool]:
    """Returns (checkpoints reflecting the current plan, immediate_attention_required).

    P1-06: this replaces the commitment's existing PENDING AUTO_RULE
    checkpoints with the freshly computed plan instead of piling new ones on
    top every time control settings change (e.g. 2 days -> 3 days lead
    time). A still-pending AUTO_RULE checkpoint that keeps a slot in the new
    plan is moved in place (CHECKPOINT_AUTO_RECALCULATED, same as a
    reschedule); one with no slot left in the new plan is removed with no
    history entry (same convention as deleting any other never-actioned
    PENDING checkpoint). COMPLETED/SKIPPED checkpoints and MANUAL
    checkpoints are never touched.

    `commit=False` lets create_commitment fold this into its own single
    transaction instead of committing here independently.
    """
    if commitment.status != CommitmentStatus.ACTIVE:
        raise ConflictError("Cannot generate a checkpoint for a commitment that is not ACTIVE")
    if commitment.deadline is None:
        raise ValidationAppError("Cannot auto-generate a checkpoint for a commitment without a deadline")

    if lead_time_days is not None:
        scheduled_times = [commitment.deadline - timedelta(days=lead_time_days)]
    else:
        scheduled_times = _default_rule_schedule(commitment.deadline, reference_time, commitment.created_at)

    resolved_times: list[datetime] = []
    immediate_attention = False
    for computed_at in scheduled_times:
        if computed_at >= commitment.deadline:
            continue

        scheduled_at = computed_at
        if computed_at < commitment.created_at:
            # FR-016 / P0-04: the rule-recommended date is earlier than the
            # commitment even existed — clamp it to created_at rather than
            # silently dropping the checkpoint, so the signal survives as a
            # real PENDING row (and therefore CHECK_DUE control health)
            # instead of only a one-off flag in this response.
            scheduled_at = commitment.created_at
            immediate_attention = True
        resolved_times.append(scheduled_at)

    stale = [
        cp
        for cp in commitment.checkpoints
        if cp.status == CheckpointStatus.PENDING and cp.source_type == CheckpointSourceType.AUTO_RULE
    ]

    result: list[CommitmentCheckpoint] = []
    for scheduled_at in resolved_times:
        already_present = next((cp for cp in commitment.checkpoints if cp.scheduled_at == scheduled_at), None)
        if already_present is not None:
            if already_present in stale:
                stale.remove(already_present)
            result.append(already_present)
        elif stale:
            checkpoint = stale.pop(0)
            old_scheduled_at = checkpoint.scheduled_at
            checkpoint.scheduled_at = scheduled_at
            _add_history(
                db,
                commitment.id,
                HistoryEventType.CHECKPOINT_AUTO_RECALCULATED,
                {"scheduled_at": old_scheduled_at.isoformat()},
                {"scheduled_at": scheduled_at.isoformat()},
            )
            result.append(checkpoint)
        else:
            suggestion = _suggestion_provider.suggest(commitment, scheduled_at, reference_time)
            checkpoint = CommitmentCheckpoint(
                commitment_id=commitment.id,
                title=suggestion.title,
                question=suggestion.question,
                reason=suggestion.reason,
                scheduled_at=scheduled_at,
                source_type=CheckpointSourceType.AUTO_RULE,
            )
            db.add(checkpoint)
            db.flush()
            commitment.checkpoints.append(checkpoint)
            _add_history(db, commitment.id, HistoryEventType.CHECKPOINT_CREATED, None, _checkpoint_snapshot(checkpoint))
            result.append(checkpoint)

        if scheduled_at <= reference_time:
            immediate_attention = True

    for leftover in stale:
        commitment.checkpoints.remove(leftover)
        db.delete(leftover)

    if question_override is not None or reason_override is not None:
        for checkpoint in result:
            if question_override is not None:
                checkpoint.question = question_override
            if reason_override is not None:
                checkpoint.reason = reason_override

    db.flush()

    if commit:
        db.commit()
        for cp in result:
            db.refresh(cp)

    return result, immediate_attention


def disable_auto_control(db: Session, commitment: Commitment, now: datetime) -> None:
    """P1-06: turning off preliminary control (lead_time_days -> null) skips
    every still-PENDING AUTO_RULE checkpoint rather than leaving it dangling
    with control nominally disabled. MANUAL checkpoints and any already
    COMPLETED/SKIPPED one are left untouched — only the auto-generated plan
    is being turned off."""
    for checkpoint in commitment.checkpoints:
        if checkpoint.status != CheckpointStatus.PENDING or checkpoint.source_type != CheckpointSourceType.AUTO_RULE:
            continue
        checkpoint.status = CheckpointStatus.SKIPPED
        checkpoint.skipped_at = now
        checkpoint.action_note = "Предварительный контроль отключен"
        _add_history(
            db,
            commitment.id,
            HistoryEventType.CHECKPOINT_SKIPPED,
            None,
            {"title": checkpoint.title, "reason": checkpoint.action_note},
        )


def recalculate_auto_checkpoints(
    db: Session, commitment: Commitment, old_deadline: datetime | None, new_deadline: datetime | None
) -> bool:
    """FR-020: shift each still-pending AUTO_RULE checkpoint by the same gap
    it originally held relative to the old deadline, so a lead time of "2
    days before" stays "2 days before" the new deadline. MANUAL checkpoints
    and already COMPLETED/SKIPPED ones are left untouched.

    Returns immediate_attention_required (P0-04/P1-08): shifting a
    checkpoint to before the commitment's created_at (e.g. a reschedule to a
    much closer deadline) must clamp it to created_at rather than create an
    AUTO_RULE checkpoint that predates the commitment, and that clamp must
    surface as an immediate-attention signal rather than disappear silently."""
    if old_deadline is None or new_deadline is None:
        return False

    immediate_attention = False

    for checkpoint in commitment.checkpoints:
        if checkpoint.status != CheckpointStatus.PENDING or checkpoint.source_type != CheckpointSourceType.AUTO_RULE:
            continue

        gap = old_deadline - checkpoint.scheduled_at
        new_scheduled_at = new_deadline - gap
        if new_scheduled_at < commitment.created_at:
            new_scheduled_at = commitment.created_at
            immediate_attention = True

        old_scheduled_at = checkpoint.scheduled_at
        checkpoint.scheduled_at = new_scheduled_at
        _add_history(
            db,
            commitment.id,
            HistoryEventType.CHECKPOINT_AUTO_RECALCULATED,
            {"scheduled_at": old_scheduled_at.isoformat()},
            {"scheduled_at": new_scheduled_at.isoformat()},
        )

    return immediate_attention


def manual_checkpoints_after(commitment: Commitment, deadline: datetime | None) -> list[CommitmentCheckpoint]:
    """P1-08: MANUAL checkpoints are never moved by a reschedule, so a new,
    earlier deadline can leave one scheduled after the deadline it is meant
    to check on. Surface those instead of leaving the mismatch silent."""
    if deadline is None:
        return []
    return [
        cp
        for cp in commitment.checkpoints
        if cp.status == CheckpointStatus.PENDING
        and cp.source_type == CheckpointSourceType.MANUAL
        and cp.scheduled_at > deadline
    ]


# --- Control health (FR-019) -------------------------------------------


def compute_control_health(commitment: Commitment, now: datetime) -> ControlHealth:
    """FR-019, with an explicit priority order for the (rare) case where more
    than one condition is true at once: BLOCKED > AT_RISK > CHECK_DUE >
    ON_TRACK — the same order the Today screen uses to group commitments
    that need attention."""
    if commitment.status != CommitmentStatus.ACTIVE:
        return ControlHealth.ON_TRACK

    assessed = [cp for cp in commitment.checkpoints if cp.assessed_at is not None]
    if assessed:
        latest = max(assessed, key=lambda cp: cp.assessed_at)
        if latest.assessment == CheckpointAssessment.BLOCKED:
            return ControlHealth.BLOCKED
        if latest.assessment == CheckpointAssessment.AT_RISK:
            return ControlHealth.AT_RISK

    has_due = any(
        cp.status == CheckpointStatus.PENDING and cp.scheduled_at <= now for cp in commitment.checkpoints
    )
    if has_due:
        return ControlHealth.CHECK_DUE

    return ControlHealth.ON_TRACK


def needs_attention(control_health: ControlHealth) -> bool:
    return control_health in (ControlHealth.BLOCKED, ControlHealth.AT_RISK, ControlHealth.CHECK_DUE)
