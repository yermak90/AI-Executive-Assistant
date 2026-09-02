import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.commitment import CommitmentStatus, Direction
from app.schemas.commitment import (
    Bucket,
    CommitmentCreate,
    CommitmentDetail,
    CommitmentHistoryRead,
    CommitmentRead,
    CommitmentUpdate,
    ControlHealth,
    RescheduleRequest,
    RescheduleResponse,
)
from app.services import commitments as commitments_service
from app.services.commitments import CommitmentFilters

router = APIRouter(prefix="/commitments", tags=["commitments"])


@router.get("", response_model=list[CommitmentRead])
def list_commitments(
    direction: Direction | None = None,
    status: CommitmentStatus | None = None,
    project_id: uuid.UUID | None = None,
    person_id: uuid.UUID | None = None,
    bucket: Bucket | None = Query(default=None, description="overdue|today|tomorrow|later|no_deadline"),
    control_health: ControlHealth | None = None,
    archive: bool = False,
    db: Session = Depends(get_db),
) -> list[CommitmentRead]:
    filters = CommitmentFilters(
        direction=direction,
        status=status,
        project_id=project_id,
        person_id=person_id,
        bucket=bucket,
        control_health=control_health,
        archive=archive,
    )
    commitments = commitments_service.list_commitments(db, filters)
    return [commitments_service.to_commitment_read(c) for c in commitments]


@router.post("", response_model=CommitmentDetail, status_code=201)
def create_commitment(data: CommitmentCreate, db: Session = Depends(get_db)) -> CommitmentDetail:
    commitment = commitments_service.create_commitment(db, data)
    return commitments_service.to_commitment_detail(commitment)


@router.get("/{commitment_id}", response_model=CommitmentDetail)
def get_commitment(commitment_id: uuid.UUID, db: Session = Depends(get_db)) -> CommitmentDetail:
    commitment = commitments_service.get_commitment_or_raise(db, commitment_id)
    return commitments_service.to_commitment_detail(commitment)


@router.patch("/{commitment_id}", response_model=CommitmentDetail)
def update_commitment(
    commitment_id: uuid.UUID, data: CommitmentUpdate, db: Session = Depends(get_db)
) -> CommitmentDetail:
    commitment = commitments_service.update_commitment(db, commitment_id, data)
    return commitments_service.to_commitment_detail(commitment)


@router.post("/{commitment_id}/complete", response_model=CommitmentDetail)
def complete_commitment(commitment_id: uuid.UUID, db: Session = Depends(get_db)) -> CommitmentDetail:
    commitment = commitments_service.complete_commitment(db, commitment_id)
    return commitments_service.to_commitment_detail(commitment)


@router.post("/{commitment_id}/reschedule", response_model=RescheduleResponse)
def reschedule_commitment(
    commitment_id: uuid.UUID, data: RescheduleRequest, db: Session = Depends(get_db)
) -> RescheduleResponse:
    commitment, immediate_attention, manual_after = commitments_service.reschedule_commitment(
        db, commitment_id, data.deadline
    )
    return RescheduleResponse(
        commitment=commitments_service.to_commitment_detail(commitment),
        immediate_attention_required=immediate_attention,
        manual_checkpoints_after_deadline=list(manual_after),
    )


@router.post("/{commitment_id}/cancel", response_model=CommitmentDetail)
def cancel_commitment(commitment_id: uuid.UUID, db: Session = Depends(get_db)) -> CommitmentDetail:
    commitment = commitments_service.cancel_commitment(db, commitment_id)
    return commitments_service.to_commitment_detail(commitment)


@router.get("/{commitment_id}/history", response_model=list[CommitmentHistoryRead])
def get_commitment_history(commitment_id: uuid.UUID, db: Session = Depends(get_db)) -> list[CommitmentHistoryRead]:
    commitment = commitments_service.get_commitment_or_raise(db, commitment_id)
    return [CommitmentHistoryRead.model_validate(h) for h in commitment.history]
