"""P0-1: an old Sprint 1 database (schema at revision 8022bd0e9e5b, with real
data in it) must upgrade to head without losing anything. This is the
regression test for the "reset the database" anti-pattern — the migration
chain must be purely additive from that revision forward.
"""

import os
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from tests.conftest import engine as test_engine

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _alembic_config() -> Config:
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "app", "db", "migrations"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    return cfg


def _wipe_everything() -> None:
    with test_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


def test_old_schema_data_survives_upgrade_to_head():
    _wipe_everything()
    cfg = _alembic_config()

    # 1. Build the database exactly as an existing Sprint 1 deployment would
    # have it: only the original migration applied.
    command.upgrade(cfg, "8022bd0e9e5b")

    person_id = uuid.uuid4()
    project_id = uuid.uuid4()
    commitment_id = uuid.uuid4()
    history_id = uuid.uuid4()

    with test_engine.begin() as conn:
        conn.execute(
            text("INSERT INTO people (id, name, created_at, updated_at) VALUES (:id, :name, now(), now())"),
            {"id": person_id, "name": "Аян"},
        )
        conn.execute(
            text(
                "INSERT INTO projects (id, name, is_active, created_at, updated_at) "
                "VALUES (:id, :name, true, now(), now())"
            ),
            {"id": project_id, "name": "Детский сад"},
        )
        conn.execute(
            text(
                "INSERT INTO commitments "
                "(id, title, owner_person_id, project_id, direction, status, source_type, deadline, "
                " created_at, updated_at) "
                "VALUES (:id, :title, :owner, :project, 'OWED_TO_ME', 'ACTIVE', 'MANUAL', "
                " now() + interval '1 day', now(), now())"
            ),
            {"id": commitment_id, "title": "Получить стоимость ворот", "owner": person_id, "project": project_id},
        )
        conn.execute(
            text(
                "INSERT INTO commitment_history (id, commitment_id, event_type, new_value, created_at) "
                "VALUES (:id, :commitment_id, 'CREATED', '{\"title\": \"test\"}'::jsonb, now())"
            ),
            {"id": history_id, "commitment_id": commitment_id},
        )

    # 2. Upgrade to head — this must be purely additive, never a reset.
    command.upgrade(cfg, "head")

    # 3. All original rows and values must still be there.
    with test_engine.connect() as conn:
        person = conn.execute(text("SELECT name FROM people WHERE id = :id"), {"id": person_id}).one()
        assert person.name == "Аян"

        project = conn.execute(text("SELECT name FROM projects WHERE id = :id"), {"id": project_id}).one()
        assert project.name == "Детский сад"

        commitment = conn.execute(
            text("SELECT title, direction, status, counterparty_person_id, source_text, lead_time_days "
                 "FROM commitments WHERE id = :id"),
            {"id": commitment_id},
        ).one()
        assert commitment.title == "Получить стоимость ворот"
        assert commitment.direction == "OWED_TO_ME"
        assert commitment.status == "ACTIVE"
        # New columns exist and default to NULL for pre-existing rows.
        assert commitment.counterparty_person_id is None
        assert commitment.source_text is None
        assert commitment.lead_time_days is None

        history = conn.execute(
            text("SELECT event_type, new_value FROM commitment_history WHERE id = :id"), {"id": history_id}
        ).one()
        assert history.event_type == "CREATED"
        assert history.new_value == {"title": "test"}

        # The new checkpoints table exists and is usable going forward.
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            )
        }
        assert "commitment_checkpoints" in tables

    # Leave the test database at head for every other test in the suite.
    _wipe_everything()
    command.upgrade(cfg, "head")
