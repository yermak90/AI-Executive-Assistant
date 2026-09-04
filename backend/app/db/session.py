from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        # A read-only request path (list/get) can leave an implicit
        # transaction open under autocommit=False without ever calling
        # commit()/rollback() itself. Always roll back before closing so the
        # connection goes back to the pool clean instead of "idle in
        # transaction" and holding row/table locks — this matters more now
        # that a request can carry a background task (Sprint 2 voice
        # capture processing), which defers this cleanup until the
        # background task finishes rather than right after the response.
        db.rollback()
        db.close()
