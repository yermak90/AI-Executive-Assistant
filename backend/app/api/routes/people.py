import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.commitment import Commitment, CommitmentStatus
from app.models.person import Person
from app.schemas.person import PersonCreate, PersonUpdate, PersonWithStats

router = APIRouter(prefix="/people", tags=["people"])


def _active_counts(db: Session) -> dict[uuid.UUID, int]:
    rows = db.execute(
        select(Commitment.owner_person_id, func.count(Commitment.id))
        .where(Commitment.status == CommitmentStatus.ACTIVE, Commitment.owner_person_id.is_not(None))
        .group_by(Commitment.owner_person_id)
    ).all()
    return {person_id: count for person_id, count in rows}


def _to_person_with_stats(person: Person, counts: dict[uuid.UUID, int]) -> PersonWithStats:
    return PersonWithStats(
        id=person.id,
        name=person.name,
        notes=person.notes,
        created_at=person.created_at,
        updated_at=person.updated_at,
        active_commitments_count=counts.get(person.id, 0),
    )


@router.get("", response_model=list[PersonWithStats])
def list_people(db: Session = Depends(get_db)) -> list[PersonWithStats]:
    people = list(db.execute(select(Person).order_by(Person.name)).scalars().all())
    counts = _active_counts(db)
    return [_to_person_with_stats(p, counts) for p in people]


@router.post("", response_model=PersonWithStats, status_code=201)
def create_person(data: PersonCreate, db: Session = Depends(get_db)) -> PersonWithStats:
    person = Person(name=data.name, notes=data.notes)
    db.add(person)
    db.commit()
    db.refresh(person)
    return _to_person_with_stats(person, {})


@router.get("/{person_id}", response_model=PersonWithStats)
def get_person(person_id: uuid.UUID, db: Session = Depends(get_db)) -> PersonWithStats:
    person = db.get(Person, person_id)
    if person is None:
        raise NotFoundError(f"Person '{person_id}' not found")
    return _to_person_with_stats(person, _active_counts(db))


@router.patch("/{person_id}", response_model=PersonWithStats)
def update_person(person_id: uuid.UUID, data: PersonUpdate, db: Session = Depends(get_db)) -> PersonWithStats:
    person = db.get(Person, person_id)
    if person is None:
        raise NotFoundError(f"Person '{person_id}' not found")

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(person, field, value)

    db.commit()
    db.refresh(person)
    return _to_person_with_stats(person, _active_counts(db))
