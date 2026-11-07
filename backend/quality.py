"""Metadata for user-supplied records; no synthetic real-time values."""
from datetime import datetime, timezone


def snapshot_quality(as_of: datetime, now: datetime | None = None, limit_hours: int = 72) -> dict:
    if as_of.tzinfo is None:
        raise ValueError("Snapshot must have timezone")
    reference = now or datetime.now(timezone.utc)
    elapsed = (reference - as_of).total_seconds()
    if elapsed < -600:
        raise ValueError("Snapshot cannot be from the future")
    age_hours = max(0, round(elapsed / 3600, 1))
    return {"age_hours": age_hours, "outdated": elapsed > limit_hours * 3600,
            "threshold_hours": limit_hours}
