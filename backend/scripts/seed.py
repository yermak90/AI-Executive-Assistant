"""Seed the database with demo people, projects, commitments and checkpoints.

Dates are generated relative to the current date (in the application
timezone) so the Today / Control screens stay meaningful whenever this is
run.

This is a destructive demo/reset operation (PRD section 17): it will not
silently wipe an existing database. If any people, projects or commitments
already exist, it aborts unless run with --reset.
"""

import sys
from datetime import timedelta

from sqlalchemy import delete, select, func

from app.core.timezone import now as tz_now
from app.db.session import SessionLocal
from app.models.commitment import Commitment, Direction
from app.models.commitment_checkpoint import CommitmentCheckpoint
from app.models.commitment_history import CommitmentHistory
from app.models.person import Person
from app.models.project import Project
from app.schemas.checkpoint import CheckpointAssessRequest, CheckpointCreate
from app.schemas.commitment import CommitmentCreate
from app.services.checkpoints import assess_checkpoint, create_manual_checkpoint
from app.services.commitments import create_commitment


def _has_existing_data(db) -> bool:
    count = db.execute(select(func.count()).select_from(Commitment)).scalar_one()
    return count > 0


def clear_existing(db) -> None:
    db.execute(delete(CommitmentCheckpoint))
    db.execute(delete(CommitmentHistory))
    db.execute(delete(Commitment))
    db.execute(delete(Project))
    db.execute(delete(Person))
    db.commit()


def seed() -> None:
    force = "--reset" in sys.argv
    db = SessionLocal()
    try:
        if _has_existing_data(db) and not force:
            print(
                "Database already has data. Refusing to reset it silently.\n"
                "Re-run with `python -m scripts.seed --reset` if you really want to "
                "wipe and recreate the demo dataset."
            )
            sys.exit(1)

        clear_existing(db)

        people = {name: Person(name=name) for name in ["Аян", "Руслан", "Марина", "Ермек", "Асет"]}
        db.add_all(people.values())

        projects = {name: Project(name=name) for name in ["Детский сад", "Astana Plaza", "Медиафасад"]}
        db.add_all(projects.values())
        db.commit()

        today = tz_now()

        def at(base_date, hour: int, minute: int = 0):
            return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # --- Commitments covering every bucket + both directions ----------
        commitments_data = [
            # overdue
            CommitmentCreate(
                title="Получить стоимость ворот",
                owner_person_id=people["Аян"].id,
                project_id=projects["Детский сад"].id,
                direction=Direction.OWED_TO_ME,
                deadline=at(today - timedelta(days=1), 12, 0),
            ),
            # today
            CommitmentCreate(
                title="Согласовать чертежи",
                owner_person_id=people["Руслан"].id,
                project_id=projects["Astana Plaza"].id,
                direction=Direction.OWED_TO_ME,
                deadline=at(today, 18, 0) if at(today, 18, 0) > today else today + timedelta(hours=2),
            ),
            # tomorrow, TEAM direction
            CommitmentCreate(
                title="Завершить монтаж",
                owner_person_id=people["Руслан"].id,
                project_id=projects["Медиафасад"].id,
                direction=Direction.TEAM,
                deadline=at(today + timedelta(days=1), 14, 0),
            ),
            # today, I_OWE (no owner person - implicitly the current user)
            CommitmentCreate(
                title="Отправить КП заказчику",
                project_id=projects["Astana Plaza"].id,
                direction=Direction.I_OWE,
                deadline=at(today, 18, 0) if at(today, 18, 0) > today else today + timedelta(hours=3),
            ),
            # later (well beyond tomorrow)
            CommitmentCreate(
                title="Подготовить финальный отчет",
                owner_person_id=people["Ермек"].id,
                project_id=projects["Медиафасад"].id,
                direction=Direction.TEAM,
                deadline=today + timedelta(days=10),
            ),
            # no deadline
            CommitmentCreate(
                title="Согласовать смету",
                owner_person_id=people["Марина"].id,
                project_id=projects["Детский сад"].id,
                direction=Direction.OWED_TO_ME,
                deadline=None,
            ),
            # I_OWE with a counterparty, for a long task with preliminary
            # control (auto-rule checkpoint via lead_time_days)
            CommitmentCreate(
                title="Купить материалы",
                counterparty_person_id=people["Асет"].id,
                project_id=projects["Детский сад"].id,
                direction=Direction.I_OWE,
                deadline=today + timedelta(days=5),
                enable_control=True,
                lead_time_days=2,
            ),
        ]

        created = [create_commitment(db, data) for data in commitments_data]
        by_title = {c.title: c for c in created}

        # --- Manual checkpoint + AT_RISK assessment, so "Требует внимания"
        # has something to show out of the box.
        at_risk_commitment = by_title["Завершить монтаж"]
        checkpoint = create_manual_checkpoint(
            db,
            at_risk_commitment,
            CheckpointCreate(
                title="Проверить наличие оборудования",
                question="Оборудование на объекте?",
                scheduled_at=tz_now(),
            ),
        )
        assess_checkpoint(
            db,
            checkpoint,
            CheckpointAssessRequest(assessment="AT_RISK", assessment_note="Поставщик не подтвердил наличие"),
        )

        print(
            f"Seeded {len(people)} people, {len(projects)} projects, "
            f"{len(commitments_data)} commitments (covering every bucket + a checkpoint at risk)."
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed()
