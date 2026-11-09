"""Metadata for user-supplied records; no synthetic real-time values."""
from datetime import datetime, timezone
import math


def snapshot_quality(as_of: datetime, now: datetime | None = None, limit_hours: int = 72) -> dict:
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("Snapshot must have timezone")
    if isinstance(limit_hours, bool) or not isinstance(limit_hours, (int, float)) or not math.isfinite(limit_hours) or limit_hours <= 0 or limit_hours > 87600:
        raise ValueError("Invalid freshness threshold")
    reference = datetime.now(timezone.utc) if now is None else now
    if not isinstance(reference, datetime) or reference.tzinfo is None or reference.utcoffset() is None:
        raise ValueError("Reference must have timezone")
    elapsed = (reference - as_of).total_seconds()
    if elapsed < -600:
        raise ValueError("Snapshot cannot be from the future")
    age_hours = max(0, round(elapsed / 3600, 1))
    return {"age_hours": age_hours, "outdated": elapsed > limit_hours * 3600,
            "threshold_hours": limit_hours}
