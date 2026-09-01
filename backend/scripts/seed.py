"""Seed the database with demo people, projects, and commitments.

Dates are generated relative to the current date (in the application
timezone) so the Today / Overdue screens stay meaningful whenever this is
run. Re-running this script wipes and recreates the demo dataset.
"""

from datetime import timedelta

from sqlalchemy import delete

from app.core.timezone import now as tz_now
from app.db.session import SessionLocal
from app.models.commitment import Commitment, Direction
from app.models.commitment_history import CommitmentHistory
from app.models.person import Person
from app.models.project import Project
from app.schemas.commitment import CommitmentCreate
from app.services.commitments import create_commitment


def clear_existing(db) -> None:
    db.execute(delete(CommitmentHistory))
    db.execute(delete(Commitment))
    db.execute(delete(Project))
    db.execute(delete(Person))
    db.commit()


def seed() -> None:
    db = SessionLocal()
    try:
        clear_existing(db)

        people = {name: Person(name=name) for name in ["Аян", "Руслан", "Марина", "Ермек", "Асет"]}
        db.add_all(people.values())

        projects = {
            name: Project(name=name)
            for name in ["Детский сад", "Astana Plaza", "Медиафасад"]
        }
        db.add_all(projects.values())
        db.commit()

        today = tz_now()

        def at(base_date, hour: int, minute: int = 0):
            return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

        commitments = [
            CommitmentCreate(
                title="Получить стоимость ворот",
                owner_person_id=people["Аян"].id,
                project_id=projects["Детский сад"].id,
                direction=Direction.OWED_TO_ME,
                deadline=at(today, 12, 0),
            ),
            CommitmentCreate(
                title="Согласовать чертежи",
                owner_person_id=people["Руслан"].id,
                project_id=projects["Astana Plaza"].id,
                direction=Direction.OWED_TO_ME,
                deadline=at(today, 18, 0),
            ),
            CommitmentCreate(
                title="Завершить монтаж",
                owner_person_id=people["Руслан"].id,
                project_id=projects["Медиафасад"].id,
                direction=Direction.TEAM,
                deadline=at(today - timedelta(days=1), 14, 0),
            ),
            CommitmentCreate(
                title="Отправить КП заказчику",
                owner_person_id=None,
                project_id=projects["Astana Plaza"].id,
                direction=Direction.I_OWE,
                deadline=at(today, 18, 0),
            ),
            CommitmentCreate(
                title="Завершить монтаж",
                owner_person_id=people["Руслан"].id,
                project_id=projects["Медиафасад"].id,
                direction=Direction.TEAM,
                deadline=at(today + timedelta(days=2), 0, 0),
            ),
            CommitmentCreate(
                title="Согласовать смету",
                owner_person_id=people["Марина"].id,
                project_id=projects["Детский сад"].id,
                direction=Direction.OWED_TO_ME,
                deadline=None,
            ),
        ]

        for data in commitments:
            create_commitment(db, data)

        print(f"Seeded {len(people)} people, {len(projects)} projects, {len(commitments)} commitments.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
