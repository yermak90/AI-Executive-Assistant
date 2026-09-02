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


def _apply_checkpoint_field_overrides(
    db: Session, commitment: Commitment, checkpoint: CommitmentCheckpoint, field_overrides: dict[str, object]
) -> None:
    """Applies question/reason overrides to an *existing* (reused or
    recalculated) checkpoint with real change-tracking: only fields that
    actually change produce a CHECKPOINT_UPDATED entry (old_value/new_value
    per field, no-op suppressed), and an explicit None in field_overrides is
    a real clear-to-null rather than "leave untouched" — the caller decides
    that by omitting the key entirely instead."""
    if not field_overrides:
        return
    changed_old: dict[str, object] = {}
    changed_new: dict[str, object] = {}
    for field, new_value in field_overrides.items():
        old_value = getattr(checkpoint, field)
        if new_value == old_value:
            continue
        changed_old[field] = old_value
        changed_new[field] = new_value
        setattr(checkpoint, field, new_value)
    if changed_new:
        _add_history(db, commitment.id, HistoryEventType.CHECKPOINT_UPDATED, changed_old, changed_new)


def generate_auto_checkpoints(
    db: Session,
    commitment: Commitment,
    lead_time_days: int | None,
    reference_time: datetime,
    field_overrides: dict[str, object] | None = None,
    commit: bool = True,
) -> tuple[list[CommitmentCheckpoint], bool]:
    """Returns (checkpoints reflecting the current plan, immediate_attention_required).

    P1-06: this replaces the commitment's existing PENDING AUTO_RULE
    checkpoints with the freshly computed plan instead of piling new ones on
    top every time control settings change (e.g. 2 days -> 3 days lead
    time). Only a PENDING AUTO_RULE checkpoint is ever reused, moved, or
    replaced — a still-pending one that keeps a slot in the new plan is
    moved in place (CHECKPOINT_AUTO_RECALCULATED, same as a reschedule) or,
    if it already sits exactly on the new slot, left as-is; one with no slot
    left in the new plan is removed with no history entry (same convention
    as deleting any other never-actioned PENDING checkpoint).

    MANUAL checkpoints and any COMPLETED/SKIPPED checkpoint (whatever their
    source) are never touched, moved, or returned as part of the generated
    plan. If the newly computed schedule would land exactly on one of them,
    that is a real scheduling conflict: raise ValidationAppError (422)
    *before* mutating anything, so the whole call — including any
    lead_time_days change a caller already applied to `commitment` in the
    same transaction — rolls back with no partial effect.

    field_overrides, when given, sets question/reason (or any other simple
    checkpoint field) on the checkpoint(s) this call touches: a key present
    with value None is an explicit clear, a key omitted is left untouched.
    On a freshly created checkpoint this is baked into its initial values
    (no separate history entry); on a reused/recalculated one it goes
    through the same real old/new change-tracking as a manual edit.

    `commit=False` lets a caller (create_commitment, update_control_settings)
    fold this into its own single transaction instead of committing here
    independently.
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
    protected = [cp for cp in commitment.checkpoints if cp not in stale]

    # Conflict pass first, over ALL resolved times, before any mutation:
    # a MANUAL/COMPLETED/SKIPPED checkpoint sitting exactly on a slot the
    # new plan needs is never silently reused as "already representing" it.
    for scheduled_at in resolved_times:
        conflict = next((cp for cp in protected if cp.scheduled_at == scheduled_at), None)
        if conflict is not None:
            raise ValidationAppError(
                f"Cannot schedule an automatic checkpoint at {scheduled_at.isoformat()}: a "
                f"{conflict.source_type.value} checkpoint ({conflict.status.value.lower()}) "
                "already exists at that exact time"
            )

    field_overrides = field_overrides or {}
    remaining_stale = list(stale)
    result: list[CommitmentCheckpoint] = []
    for scheduled_at in resolved_times:
        exact_match = next((cp for cp in remaining_stale if cp.scheduled_at == scheduled_at), None)
        if exact_match is not None:
            remaining_stale.remove(exact_match)
            _apply_checkpoint_field_overrides(db, commitment, exact_match, field_overrides)
            result.append(exact_match)
        elif remaining_stale:
            checkpoint = remaining_stale.pop(0)
            old_scheduled_at = checkpoint.scheduled_at
            checkpoint.scheduled_at = scheduled_at
            _add_history(
                db,
                commitment.id,
                HistoryEventType.CHECKPOINT_AUTO_RECALCULATED,
                {"scheduled_at": old_scheduled_at.isoformat()},
                {"scheduled_at": scheduled_at.isoformat()},
            )
            _apply_checkpoint_field_overrides(db, commitment, checkpoint, field_overrides)
            result.append(checkpoint)
        else:
            suggestion = _suggestion_provider.suggest(commitment, scheduled_at, reference_time)
            checkpoint = CommitmentCheckpoint(
                commitment_id=commitment.id,
                title=suggestion.title,
                question=field_overrides.get("question", suggestion.question),
                reason=field_overrides.get("reason", suggestion.reason),
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

    for leftover in remaining_stale:
        commitment.checkpoints.remove(leftover)
        db.delete(leftover)

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

    Review follow-up: this validates the *entire* new plan before mutating
    anything. Pass 1 computes every new scheduled_at with no DB writes. Pass
    2 deterministically de-duplicates AUTO_RULE checkpoints that would land
    on the exact same instant (e.g. several all clamped to created_at): the
    one with the earliest original scheduled_at wins and gets recalculated,
    the rest are removed with no history (same convention as removing any
    other never-actioned PENDING checkpoint with no slot left in the plan).
    Pass 3 checks the surviving times against every MANUAL/COMPLETED/SKIPPED
    checkpoint and raises ValidationAppError (422) on the first collision —
    before any checkpoint has been moved, so a caller who already applied
    the deadline change to `commitment` in the same transaction rolls that
    back too. Only pass 4 writes anything.

    Returns immediate_attention_required (P0-04/P1-08): shifting a
    checkpoint to before the commitment's created_at (e.g. a reschedule to a
    much closer deadline) must clamp it to created_at rather than create an
    AUTO_RULE checkpoint that predates the commitment, and that clamp must
    surface as an immediate-attention signal rather than disappear silently."""
    if old_deadline is None or new_deadline is None:
        return False

    auto_checkpoints = [
        cp
        for cp in commitment.checkpoints
        if cp.status == CheckpointStatus.PENDING and cp.source_type == CheckpointSourceType.AUTO_RULE
    ]
    if not auto_checkpoints:
        return False

    protected = [cp for cp in commitment.checkpoints if cp not in auto_checkpoints]

    # Pass 1: compute every new scheduled_at, no mutation yet.
    immediate_attention = False
    planned: list[tuple[CommitmentCheckpoint, datetime]] = []
    for checkpoint in auto_checkpoints:
        gap = old_deadline - checkpoint.scheduled_at
        new_scheduled_at = new_deadline - gap
        if new_scheduled_at < commitment.created_at:
            new_scheduled_at = commitment.created_at
            immediate_attention = True
        planned.append((checkpoint, new_scheduled_at))

    # Pass 2: de-duplicate collisions among the newly-planned AUTO_RULE
    # times deterministically — process in original-scheduled_at order so
    # the earliest-scheduled checkpoint always wins a tie.
    planned.sort(key=lambda pair: pair[0].scheduled_at)
    seen_times: set[datetime] = set()
    deduped: list[tuple[CommitmentCheckpoint, datetime]] = []
    to_remove: list[CommitmentCheckpoint] = []
    for checkpoint, new_scheduled_at in planned:
        if new_scheduled_at in seen_times:
            to_remove.append(checkpoint)
            continue
        seen_times.add(new_scheduled_at)
        deduped.append((checkpoint, new_scheduled_at))

    # Pass 3: check the surviving plan against every protected checkpoint.
    for _checkpoint, new_scheduled_at in deduped:
        conflict = next((cp for cp in protected if cp.scheduled_at == new_scheduled_at), None)
        if conflict is not None:
            raise ValidationAppError(
                f"Cannot reschedule an automatic checkpoint to {new_scheduled_at.isoformat()}: a "
                f"{conflict.source_type.value} checkpoint ({conflict.status.value.lower()}) "
                "already exists at that exact time"
            )

    # Pass 4: everything validated — now it's safe to write.
    for checkpoint, new_scheduled_at in deduped:
        old_scheduled_at = checkpoint.scheduled_at
        if new_scheduled_at == old_scheduled_at:
            continue
        checkpoint.scheduled_at = new_scheduled_at
        _add_history(
            db,
            commitment.id,
            HistoryEventType.CHECKPOINT_AUTO_RECALCULATED,
            {"scheduled_at": old_scheduled_at.isoformat()},
            {"scheduled_at": new_scheduled_at.isoformat()},
        )

    for checkpoint in to_remove:
        commitment.checkpoints.remove(checkpoint)
        db.delete(checkpoint)

    return immediate_attention


def manual_checkpoints_after(commitment: Commitment, deadline: datetime | None) -> list[CommitmentCheckpoint]:
    """P1-08: MANUAL checkpoints are never moved by a reschedule, so a new,
    earlier deadline can leave one scheduled at-or-after the deadline it is
    meant to check on (a checkpoint scheduled for the exact deadline instant
    is no longer "before the deadline" either). Surface those instead of
    leaving the mismatch silent."""
    if deadline is None:
        return []
    return [
        cp
        for cp in commitment.checkpoints
        if cp.status == CheckpointStatus.PENDING
        and cp.source_type == CheckpointSourceType.MANUAL
        and cp.scheduled_at >= deadline
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
