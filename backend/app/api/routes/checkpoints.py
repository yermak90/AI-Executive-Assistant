import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.timezone import now as tz_now
from app.db.session import get_db
from app.schemas.checkpoint import (
    CheckpointAssessRequest,
    CheckpointCreate,
    CheckpointGenerateRequest,
    CheckpointGenerateResponse,
    CheckpointRead,
    CheckpointUpdate,
)
from app.services import checkpoints as checkpoints_service
from app.services import commitments as commitments_service

router = APIRouter(tags=["checkpoints"])


@router.get("/commitments/{commitment_id}/checkpoints", response_model=list[CheckpointRead])
def list_checkpoints(commitment_id: uuid.UUID, db: Session = Depends(get_db)) -> list[CheckpointRead]:
    commitments_service.get_commitment_or_raise(db, commitment_id)
    return checkpoints_service.list_checkpoints(db, commitment_id)


@router.post("/commitments/{commitment_id}/checkpoints", response_model=CheckpointRead, status_code=201)
def create_checkpoint(
    commitment_id: uuid.UUID, data: CheckpointCreate, db: Session = Depends(get_db)
) -> CheckpointRead:
    commitment = commitments_service.get_commitment_or_raise(db, commitment_id)
    return checkpoints_service.create_manual_checkpoint(db, commitment, data)


@router.post("/commitments/{commitment_id}/checkpoints/generate", response_model=CheckpointGenerateResponse)
def generate_checkpoints(
    commitment_id: uuid.UUID, data: CheckpointGenerateRequest, db: Session = Depends(get_db)
) -> CheckpointGenerateResponse:
    commitment = commitments_service.get_commitment_or_raise(db, commitment_id)
    lead_time_days = data.lead_time_days if data.lead_time_days is not None else commitment.lead_time_days
    created, immediate_attention = checkpoints_service.generate_auto_checkpoints(
        db,
        commitment,
        lead_time_days=lead_time_days,
        reference_time=tz_now(),
        question_override=data.question,
        reason_override=data.reason,
    )
    return CheckpointGenerateResponse(checkpoints=created, immediate_attention_required=immediate_attention)


@router.patch("/checkpoints/{checkpoint_id}", response_model=CheckpointRead)
def update_checkpoint(checkpoint_id: uuid.UUID, data: CheckpointUpdate, db: Session = Depends(get_db)) -> CheckpointRead:
    checkpoint = checkpoints_service.get_checkpoint_or_raise(db, checkpoint_id)
    return checkpoints_service.update_checkpoint(db, checkpoint, data)


@router.delete("/checkpoints/{checkpoint_id}", status_code=204)
def delete_checkpoint(checkpoint_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    checkpoint = checkpoints_service.get_checkpoint_or_raise(db, checkpoint_id)
    checkpoints_service.delete_checkpoint(db, checkpoint)


@router.post("/checkpoints/{checkpoint_id}/assess", response_model=CheckpointRead)
def assess_checkpoint(
    checkpoint_id: uuid.UUID, data: CheckpointAssessRequest, db: Session = Depends(get_db)
) -> CheckpointRead:
    checkpoint = checkpoints_service.get_checkpoint_or_raise(db, checkpoint_id)
    return checkpoints_service.assess_checkpoint(db, checkpoint, data)


@router.post("/checkpoints/{checkpoint_id}/skip", response_model=CheckpointRead)
def skip_checkpoint(checkpoint_id: uuid.UUID, db: Session = Depends(get_db)) -> CheckpointRead:
    checkpoint = checkpoints_service.get_checkpoint_or_raise(db, checkpoint_id)
    return checkpoints_service.skip_checkpoint(db, checkpoint)
