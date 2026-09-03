from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# Import models so they are registered on Base.metadata for Alembic autogenerate.
from app.models import commitment, commitment_checkpoint, commitment_history, person, project, voice_capture  # noqa: E402,F401
