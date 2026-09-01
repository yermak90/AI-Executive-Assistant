import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.timezone import now as tz_now
from app.db.session import get_db
from app.models.commitment import Commitment, CommitmentStatus
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectWithStats

router = APIRouter(prefix="/projects", tags=["projects"])


def _counts(db: Session) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, int]]:
    rows = db.execute(
        select(Commitment.project_id, Commitment.deadline).where(
            Commitment.status == CommitmentStatus.ACTIVE, Commitment.project_id.is_not(None)
        )
    ).all()

    now = tz_now()
    active: dict[uuid.UUID, int] = defaultdict(int)
    overdue: dict[uuid.UUID, int] = defaultdict(int)
    for project_id, deadline in rows:
        active[project_id] += 1
        if deadline is not None and deadline < now:
            overdue[project_id] += 1
    return active, overdue


def _to_project_with_stats(
    project: Project, active: dict[uuid.UUID, int], overdue: dict[uuid.UUID, int]
) -> ProjectWithStats:
    return ProjectWithStats(
        id=project.id,
        name=project.name,
        description=project.description,
        is_active=project.is_active,
        created_at=project.created_at,
        updated_at=project.updated_at,
        active_commitments_count=active.get(project.id, 0),
        overdue_commitments_count=overdue.get(project.id, 0),
    )


@router.get("", response_model=list[ProjectWithStats])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectWithStats]:
    projects = list(db.execute(select(Project).order_by(Project.name)).scalars().all())
    active, overdue = _counts(db)
    return [_to_project_with_stats(p, active, overdue) for p in projects]


@router.post("", response_model=ProjectWithStats, status_code=201)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)) -> ProjectWithStats:
    project = Project(name=data.name, description=data.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_project_with_stats(project, {}, {})


@router.get("/{project_id}", response_model=ProjectWithStats)
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db)) -> ProjectWithStats:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project '{project_id}' not found")
    active, overdue = _counts(db)
    return _to_project_with_stats(project, active, overdue)


@router.patch("/{project_id}", response_model=ProjectWithStats)
def update_project(project_id: uuid.UUID, data: ProjectUpdate, db: Session = Depends(get_db)) -> ProjectWithStats:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project '{project_id}' not found")

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    active, overdue = _counts(db)
    return _to_project_with_stats(project, active, overdue)
