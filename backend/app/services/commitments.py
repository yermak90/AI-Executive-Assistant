import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.timezone import is_same_local_date
from app.core.timezone import now as tz_now
from app.models.commitment import Commitment, CommitmentStatus, Direction
from app.models.commitment_history import CommitmentHistory, HistoryEventType
from app.models.person import Person
from app.models.project import Project
from app.schemas.commitment import (
    Bucket,
    CommitmentCreate,
    CommitmentDetail,
    CommitmentHistoryRead,
    CommitmentRead,
    CommitmentUpdate,
    ControlHealth,
)
from app.schemas.checkpoint import CheckpointRead
from app.schemas.person import PersonSummary
from app.schemas.project import ProjectSummary
from app.services import checkpoints as checkpoints_service

FINAL_STATUSES = (CommitmentStatus.COMPLETED, CommitmentStatus.CANCELLED)

# Fields whose changes on a general PATCH are worth recording as history,
# and how to render each value for the history payload.
_TRACKED_FIELDS = ("title", "description", "direction", "owner_person_id", "counterparty_person_id", "project_id")


@dataclass
class CommitmentFilters:
    direction: Direction | None = None
    status: CommitmentStatus | None = None
    project_id: uuid.UUID | None = None
    person_id: uuid.UUID | None = None
    bucket: Bucket | None = None
    control_health: ControlHealth | None = None
    archive: bool = False


def _with_relations(query):
    return query.options(
        selectinload(Commitment.owner_person),
        selectinload(Commitment.counterparty_person),
        selectinload(Commitment.project),
        selectinload(Commitment.history),
        selectinload(Commitment.checkpoints),
    )


def compute_bucket(commitment: Commitment, now: datetime) -> Bucket | None:
    """FR-005: every ACTIVE commitment belongs to exactly one bucket. Returns
    None for a non-ACTIVE commitment, since buckets only describe active
    control state."""
    if commitment.status != CommitmentStatus.ACTIVE:
        return None
    if commitment.deadline is None:
        return Bucket.NO_DEADLINE
    if commitment.deadline < now:
        return Bucket.OVERDUE
    if is_same_local_date(commitment.deadline, now):
        return Bucket.TODAY
    if is_same_local_date(commitment.deadline, now + timedelta(days=1)):
        return Bucket.TOMORROW
    return Bucket.LATER


def to_commitment_read(commitment: Commitment, now: datetime | None = None) -> CommitmentRead:
    now = now or tz_now()
    bucket = compute_bucket(commitment, now)
    control_health = checkpoints_service.compute_control_health(commitment, now)
    return CommitmentRead(
        id=commitment.id,
        title=commitment.title,
        description=commitment.description,
        direction=commitment.direction,
        status=commitment.status,
        source_type=commitment.source_type,
        source_text=commitment.source_text,
        deadline=commitment.deadline,
        lead_time_days=commitment.lead_time_days,
        is_overdue=bucket == Bucket.OVERDUE,
        bucket=bucket,
        control_health=control_health,
        person=PersonSummary.model_validate(commitment.owner_person) if commitment.owner_person else None,
        counterparty=PersonSummary.model_validate(commitment.counterparty_person)
        if commitment.counterparty_person
        else None,
        project=ProjectSummary.model_validate(commitment.project) if commitment.project else None,
        created_at=commitment.created_at,
        updated_at=commitment.updated_at,
        completed_at=commitment.completed_at,
        cancelled_at=commitment.cancelled_at,
    )


def to_commitment_detail(commitment: Commitment, now: datetime | None = None) -> CommitmentDetail:
    base = to_commitment_read(commitment, now)
    history = [CommitmentHistoryRead.model_validate(h) for h in commitment.history]
    checkpoints = [CheckpointRead.model_validate(cp) for cp in commitment.checkpoints]
    return CommitmentDetail(**base.model_dump(), history=history, checkpoints=checkpoints)


def _get_person_or_raise(db: Session, person_id: uuid.UUID) -> Person:
    person = db.get(Person, person_id)
    if person is None:
        raise ValidationAppError(f"Person '{person_id}' does not exist")
    return person


def _get_project_or_raise(db: Session, project_id: uuid.UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise ValidationAppError(f"Project '{project_id}' does not exist")
    return project


def get_commitment_or_raise(db: Session, commitment_id: uuid.UUID) -> Commitment:
    query = _with_relations(select(Commitment).where(Commitment.id == commitment_id))
    commitment = db.execute(query).scalar_one_or_none()
    if commitment is None:
        raise NotFoundError(f"Commitment '{commitment_id}' not found")
    return commitment


def _require_active(commitment: Commitment, action: str) -> None:
    if commitment.status != CommitmentStatus.ACTIVE:
        raise ConflictError(
            f"Cannot {action} a commitment that is already {commitment.status.value} "
            f"(only ACTIVE commitments can be {action}d)"
        )


def list_commitments(db: Session, filters: CommitmentFilters) -> list[Commitment]:
    query = _with_relations(select(Commitment))

    if filters.direction is not None:
        query = query.where(Commitment.direction == filters.direction)
    if filters.project_id is not None:
        query = query.where(Commitment.project_id == filters.project_id)
    if filters.person_id is not None:
        query = query.where(Commitment.owner_person_id == filters.person_id)

    if filters.archive:
        query = query.where(Commitment.status.in_(FINAL_STATUSES))
    elif filters.status is not None:
        query = query.where(Commitment.status == filters.status)

    query = query.order_by(Commitment.deadline.is_(None), Commitment.deadline.asc())
    commitments = list(db.execute(query).scalars().all())

    now = tz_now()
    if filters.bucket is not None:
        commitments = [c for c in commitments if compute_bucket(c, now) == filters.bucket]
    if filters.control_health is not None:
        commitments = [
            c for c in commitments if checkpoints_service.compute_control_health(c, now) == filters.control_health
        ]

    return commitments


def create_commitment(db: Session, data: CommitmentCreate) -> Commitment:
    if data.owner_person_id is not None:
        _get_person_or_raise(db, data.owner_person_id)
    if data.counterparty_person_id is not None:
        _get_person_or_raise(db, data.counterparty_person_id)
    if data.project_id is not None:
        _get_project_or_raise(db, data.project_id)

    commitment = Commitment(
        title=data.title,
        description=data.description,
        owner_person_id=data.owner_person_id,
        counterparty_person_id=data.counterparty_person_id,
        project_id=data.project_id,
        direction=data.direction,
        deadline=data.deadline,
        source_text=data.source_text,
        lead_time_days=data.lead_time_days if data.enable_control else None,
        status=CommitmentStatus.ACTIVE,
    )
    db.add(commitment)
    db.flush()

    db.add(
        CommitmentHistory(
            commitment_id=commitment.id,
            event_type=HistoryEventType.CREATED,
            old_value=None,
            new_value={
                "title": commitment.title,
                "direction": commitment.direction.value,
                "deadline": commitment.deadline.isoformat() if commitment.deadline else None,
            },
        )
    )
    db.commit()
    db.refresh(commitment)

    if data.enable_control and commitment.deadline is not None:
        checkpoints_service.generate_auto_checkpoints(
            db, commitment, lead_time_days=data.lead_time_days, reference_time=tz_now()
        )
        if data.control_question or data.control_reason:
            for cp in commitment.checkpoints:
                if data.control_question:
                    cp.question = data.control_question
                if data.control_reason:
                    cp.reason = data.control_reason
            db.commit()

    return get_commitment_or_raise(db, commitment.id)


def _render_field(field: str, value) -> object:
    if value is None:
        return None
    if hasattr(value, "value"):  # enum
        return value.value
    return str(value)


def update_commitment(db: Session, commitment_id: uuid.UUID, data: CommitmentUpdate) -> Commitment:
    commitment = get_commitment_or_raise(db, commitment_id)
    _require_active(commitment, "edit")
    updates = data.model_dump(exclude_unset=True)

    if "owner_person_id" in updates and updates["owner_person_id"] is not None:
        _get_person_or_raise(db, updates["owner_person_id"])
    if "counterparty_person_id" in updates and updates["counterparty_person_id"] is not None:
        _get_person_or_raise(db, updates["counterparty_person_id"])
    if "project_id" in updates and updates["project_id"] is not None:
        _get_project_or_raise(db, updates["project_id"])

    if "deadline" in updates and updates["deadline"] != commitment.deadline:
        old_deadline = commitment.deadline
        new_deadline = updates.pop("deadline")
        commitment.deadline = new_deadline
        db.add(
            CommitmentHistory(
                commitment_id=commitment.id,
                event_type=HistoryEventType.DEADLINE_CHANGED,
                old_value={"deadline": old_deadline.isoformat() if old_deadline else None},
                new_value={"deadline": new_deadline.isoformat() if new_deadline else None},
            )
        )
        checkpoints_service.recalculate_auto_checkpoints(db, commitment, old_deadline, new_deadline)
    else:
        updates.pop("deadline", None)

    changed_old: dict[str, object] = {}
    changed_new: dict[str, object] = {}
    for field in _TRACKED_FIELDS:
        if field not in updates:
            continue
        new_value = updates[field]
        old_value = getattr(commitment, field)
        if new_value == old_value:
            continue
        changed_old[field] = _render_field(field, old_value)
        changed_new[field] = _render_field(field, new_value)
        setattr(commitment, field, new_value)

    if "source_text" in updates and updates["source_text"] != commitment.source_text:
        commitment.source_text = updates["source_text"]

    if changed_new:
        db.add(
            CommitmentHistory(
                commitment_id=commitment.id,
                event_type=HistoryEventType.UPDATED,
                old_value=changed_old,
                new_value=changed_new,
            )
        )

    db.commit()
    return get_commitment_or_raise(db, commitment.id)


def reschedule_commitment(db: Session, commitment_id: uuid.UUID, new_deadline: datetime | None) -> Commitment:
    commitment = get_commitment_or_raise(db, commitment_id)
    _require_active(commitment, "reschedule")
    old_deadline = commitment.deadline

    commitment.deadline = new_deadline
    db.add(
        CommitmentHistory(
            commitment_id=commitment.id,
            event_type=HistoryEventType.DEADLINE_CHANGED,
            old_value={"deadline": old_deadline.isoformat() if old_deadline else None},
            new_value={"deadline": new_deadline.isoformat() if new_deadline else None},
        )
    )
    checkpoints_service.recalculate_auto_checkpoints(db, commitment, old_deadline, new_deadline)
    db.commit()
    return get_commitment_or_raise(db, commitment.id)


def complete_commitment(db: Session, commitment_id: uuid.UUID) -> Commitment:
    commitment = get_commitment_or_raise(db, commitment_id)
    _require_active(commitment, "complete")
    now = tz_now()

    commitment.status = CommitmentStatus.COMPLETED
    commitment.completed_at = now
    commitment.cancelled_at = None
    db.add(
        CommitmentHistory(
            commitment_id=commitment.id,
            event_type=HistoryEventType.COMPLETED,
            old_value=None,
            new_value={"completed_at": now.isoformat()},
        )
    )
    checkpoints_service.skip_pending_checkpoints(db, commitment, checkpoints_service.REASON_COMPLETED, now)
    db.commit()
    return get_commitment_or_raise(db, commitment.id)


def cancel_commitment(db: Session, commitment_id: uuid.UUID) -> Commitment:
    commitment = get_commitment_or_raise(db, commitment_id)
    _require_active(commitment, "cancel")
    now = tz_now()

    commitment.status = CommitmentStatus.CANCELLED
    commitment.cancelled_at = now
    commitment.completed_at = None
    db.add(
        CommitmentHistory(
            commitment_id=commitment.id,
            event_type=HistoryEventType.CANCELLED,
            old_value=None,
            new_value={"cancelled_at": now.isoformat()},
        )
    )
    checkpoints_service.skip_pending_checkpoints(db, commitment, checkpoints_service.REASON_CANCELLED, now)
    db.commit()
    return get_commitment_or_raise(db, commitment.id)
