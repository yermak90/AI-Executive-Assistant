import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.timezone import is_same_local_date
from app.core.timezone import now as tz_now
from app.models.commitment import Commitment, CommitmentStatus, Direction
from app.models.commitment_history import CommitmentHistory, HistoryEventType
from app.models.person import Person
from app.models.project import Project
from app.schemas.commitment import (
    CommitmentCreate,
    CommitmentDetail,
    CommitmentHistoryRead,
    CommitmentRead,
    CommitmentUpdate,
)
from app.schemas.person import PersonSummary
from app.schemas.project import ProjectSummary


@dataclass
class CommitmentFilters:
    direction: Direction | None = None
    status: CommitmentStatus | None = None
    project_id: uuid.UUID | None = None
    person_id: uuid.UUID | None = None
    due_today: bool = False
    due_tomorrow: bool = False
    overdue: bool = False


def _with_relations(query):
    return query.options(
        selectinload(Commitment.owner_person),
        selectinload(Commitment.project),
        selectinload(Commitment.history),
    )


def is_overdue(commitment: Commitment, now: datetime) -> bool:
    return (
        commitment.status == CommitmentStatus.ACTIVE
        and commitment.deadline is not None
        and commitment.deadline < now
    )


def is_due_today(commitment: Commitment, now: datetime) -> bool:
    return (
        commitment.status == CommitmentStatus.ACTIVE
        and commitment.deadline is not None
        and is_same_local_date(commitment.deadline, now)
    )


def is_due_tomorrow(commitment: Commitment, now: datetime) -> bool:
    return (
        commitment.status == CommitmentStatus.ACTIVE
        and commitment.deadline is not None
        and is_same_local_date(commitment.deadline, now + timedelta(days=1))
    )


def to_commitment_read(commitment: Commitment, now: datetime | None = None) -> CommitmentRead:
    now = now or tz_now()
    return CommitmentRead(
        id=commitment.id,
        title=commitment.title,
        description=commitment.description,
        direction=commitment.direction,
        status=commitment.status,
        source_type=commitment.source_type,
        deadline=commitment.deadline,
        is_overdue=is_overdue(commitment, now),
        person=PersonSummary.model_validate(commitment.owner_person) if commitment.owner_person else None,
        project=ProjectSummary.model_validate(commitment.project) if commitment.project else None,
        created_at=commitment.created_at,
        updated_at=commitment.updated_at,
        completed_at=commitment.completed_at,
        cancelled_at=commitment.cancelled_at,
    )


def to_commitment_detail(commitment: Commitment, now: datetime | None = None) -> CommitmentDetail:
    base = to_commitment_read(commitment, now)
    history = [CommitmentHistoryRead.model_validate(h) for h in commitment.history]
    return CommitmentDetail(**base.model_dump(), history=history)


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


def list_commitments(db: Session, filters: CommitmentFilters) -> list[Commitment]:
    query = _with_relations(select(Commitment))

    if filters.direction is not None:
        query = query.where(Commitment.direction == filters.direction)
    if filters.status is not None:
        query = query.where(Commitment.status == filters.status)
    if filters.project_id is not None:
        query = query.where(Commitment.project_id == filters.project_id)
    if filters.person_id is not None:
        query = query.where(Commitment.owner_person_id == filters.person_id)

    query = query.order_by(Commitment.deadline.is_(None), Commitment.deadline.asc())
    commitments = list(db.execute(query).scalars().all())

    now = tz_now()
    if filters.due_today:
        commitments = [c for c in commitments if is_due_today(c, now)]
    if filters.due_tomorrow:
        commitments = [c for c in commitments if is_due_tomorrow(c, now)]
    if filters.overdue:
        commitments = [c for c in commitments if is_overdue(c, now)]

    return commitments


def create_commitment(db: Session, data: CommitmentCreate) -> Commitment:
    if data.owner_person_id is not None:
        _get_person_or_raise(db, data.owner_person_id)
    if data.project_id is not None:
        _get_project_or_raise(db, data.project_id)

    commitment = Commitment(
        title=data.title,
        description=data.description,
        owner_person_id=data.owner_person_id,
        project_id=data.project_id,
        direction=data.direction,
        deadline=data.deadline,
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
    return get_commitment_or_raise(db, commitment.id)


def update_commitment(db: Session, commitment_id: uuid.UUID, data: CommitmentUpdate) -> Commitment:
    commitment = get_commitment_or_raise(db, commitment_id)
    updates = data.model_dump(exclude_unset=True)

    if "owner_person_id" in updates and updates["owner_person_id"] is not None:
        _get_person_or_raise(db, updates["owner_person_id"])
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

    other_fields = {k: v for k, v in updates.items() if k != "deadline"}
    if other_fields:
        for field, value in other_fields.items():
            setattr(commitment, field, value)
        db.add(
            CommitmentHistory(
                commitment_id=commitment.id,
                event_type=HistoryEventType.UPDATED,
                old_value=None,
                new_value=other_fields,
            )
        )

    db.commit()
    return get_commitment_or_raise(db, commitment.id)


def reschedule_commitment(db: Session, commitment_id: uuid.UUID, new_deadline: datetime | None) -> Commitment:
    commitment = get_commitment_or_raise(db, commitment_id)
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
    db.commit()
    return get_commitment_or_raise(db, commitment.id)


def complete_commitment(db: Session, commitment_id: uuid.UUID) -> Commitment:
    commitment = get_commitment_or_raise(db, commitment_id)
    now = tz_now()

    commitment.status = CommitmentStatus.COMPLETED
    commitment.completed_at = now
    db.add(
        CommitmentHistory(
            commitment_id=commitment.id,
            event_type=HistoryEventType.COMPLETED,
            old_value=None,
            new_value={"completed_at": now.isoformat()},
        )
    )
    db.commit()
    return get_commitment_or_raise(db, commitment.id)


def cancel_commitment(db: Session, commitment_id: uuid.UUID) -> Commitment:
    commitment = get_commitment_or_raise(db, commitment_id)
    now = tz_now()

    commitment.status = CommitmentStatus.CANCELLED
    commitment.cancelled_at = now
    db.add(
        CommitmentHistory(
            commitment_id=commitment.id,
            event_type=HistoryEventType.CANCELLED,
            old_value=None,
            new_value={"cancelled_at": now.isoformat()},
        )
    )
    db.commit()
    return get_commitment_or_raise(db, commitment.id)
