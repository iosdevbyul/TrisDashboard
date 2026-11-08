"""Optional local workout export, without HealthKit or remote credentials."""
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _reject_nonstandard_constant(value):
    raise ValueError("Non-standard JSON numeric constant: " + value)


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate workout JSON key")
        result[key] = value
    return result


def load_fitness(path: Path, today: date | None = None) -> dict:
    if path.stat().st_size > 128 * 1024:
        raise ValueError("Workout file too large")
    payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys,
                         parse_constant=_reject_nonstandard_constant)
    if not isinstance(payload, dict) or not isinstance(payload.get("workouts"), list):
        raise ValueError("Expected workouts array")
    workouts = payload["workouts"]
    if len(workouts) > 500:
        raise ValueError("Too many workouts")
    reference = today or date.today()
    start = reference - timedelta(days=6)
    weekly = []
    daily = {(start + timedelta(days=index)).isoformat():
             {"sessions": 0, "duration_minutes": 0, "distance_km": 0.0}
             for index in range(7)}
    totals = {"sessions": 0, "minutes": 0, "distance_km": 0.0}
    seen_ids = set()
    stable_id_count = 0
    for workout in workouts:
        if not isinstance(workout, dict):
            raise ValueError("Invalid workout")
        day_text = workout.get("date")
        kind = workout.get("type")
        minutes = workout.get("duration_minutes")
        distance = workout.get("distance_km", 0)
        if not isinstance(day_text, str) or not isinstance(kind, str) or not 1 <= len(kind) <= 32:
            raise ValueError("Invalid workout fields")
        if not _DATE_RE.fullmatch(day_text):
            raise ValueError("Invalid workout date")
        workout_day = date.fromisoformat(day_text)
        if workout_day > reference:
            raise ValueError("Future workout dates are not allowed")
        if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ -_" for c in kind):
            raise ValueError("Invalid workout type")
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not 0 <= minutes <= 1440:
            raise ValueError("Invalid duration")
        if isinstance(distance, bool) or not isinstance(distance, (int, float)) or not 0 <= distance <= 1000:
            raise ValueError("Invalid distance")
        if not (float("-inf") < float(minutes) < float("inf") and float("-inf") < float(distance) < float("inf")):
            raise ValueError("Nonfinite measurement")
        session_id = workout.get("session_id")
        if session_id is not None and (
                not isinstance(session_id, str) or not 1 <= len(session_id) <= 100
                or not all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_:." for c in session_id)):
            raise ValueError("Invalid session ID")
        if session_id is not None:
            if session_id in seen_ids:
                raise ValueError("Duplicate workout session ID")
            seen_ids.add(session_id)
            stable_id_count += 1
        if start <= workout_day <= reference:
            weekly.append({"date": workout_day.isoformat(), "type": kind, "duration_minutes": minutes, "distance_km": distance})
            totals["sessions"] += 1
            totals["minutes"] += minutes
            totals["distance_km"] += distance
            day_summary = daily[workout_day.isoformat()]
            day_summary["sessions"] += 1
            day_summary["duration_minutes"] += minutes
            day_summary["distance_km"] += distance
    for day_summary in daily.values():
        day_summary["duration_minutes"] = round(day_summary["duration_minutes"], 1)
        day_summary["distance_km"] = round(day_summary["distance_km"], 2)
    weekly.sort(key=lambda item: item["date"], reverse=True)
    active_days = sum(1 for day in daily.values() if day["sessions"] > 0)
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age_hours = max(0.0, (datetime.now(timezone.utc) - modified).total_seconds()) / 3600
    return {"available": True, "configured": True, "source": "manual_export",
            "file_updated_utc": modified.isoformat(),
            "file_age_hours": round(age_hours, 1),
            "file_older_than_week": age_hours > 168,
            "period_start": start.isoformat(), "period_end": reference.isoformat(),
            "active_days": active_days,
            "summary": {"sessions": totals["sessions"], "duration_minutes": round(totals["minutes"], 1),
                        "distance_km": round(totals["distance_km"], 2)},
            "recent": weekly[:5], "daily": [
                {"date": day, **summary} for day, summary in sorted(daily.items())
            ], "stale": False,
            "total_history_count": len(workouts),
            "stable_id_count": stable_id_count}


def fitness() -> dict:
    location = os.environ.get("TRIS_FITNESS_FILE", "").strip()
    if not location:
        return {"available": False, "configured": False, "stale": False}
    try:
        return load_fitness(Path(location).expanduser())
    except (OSError, ValueError, TypeError):
        return {"available": False, "configured": True, "stale": True}
