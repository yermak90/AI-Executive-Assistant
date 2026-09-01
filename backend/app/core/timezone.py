from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings

app_zone = ZoneInfo(settings.app_timezone)


def now() -> datetime:
    """Current time, timezone-aware, in the application timezone."""
    return datetime.now(app_zone)


def is_same_local_date(value: datetime, reference: datetime) -> bool:
    """Compare two timezone-aware datetimes by their calendar date in the
    application timezone. Never assume UTC calendar dates in business rules."""
    return value.astimezone(app_zone).date() == reference.astimezone(app_zone).date()
