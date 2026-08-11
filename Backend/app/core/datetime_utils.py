from datetime import datetime, timezone


def as_utc(value: datetime | None) -> datetime | None:
    """Normalize SQLite-naive and timezone-aware database values to UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
