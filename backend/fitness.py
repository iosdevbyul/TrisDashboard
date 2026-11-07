"""Optional local workout export, without HealthKit or remote credentials."""
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path


def load_fitness(path: Path, today: date | None = None) -> dict:
    if path.stat().st_size > 128 * 1024:
        raise ValueError("Workout file too large")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("workouts"), list):
        raise ValueError("Expected workouts array")
    workouts = payload["workouts"]
    if len(workouts) > 500:
        raise ValueError("Too many workouts")
    reference = today or date.today()
    start = reference - timedelta(days=6)
    weekly = []
    totals = {"sessions": 0, "minutes": 0, "distance_km": 0.0}
    for workout in workouts:
        if not isinstance(workout, dict):
            raise ValueError("Invalid workout")
        day_text = workout.get("date")
        kind = workout.get("type")
        minutes = workout.get("duration_minutes")
        distance = workout.get("distance_km", 0)
        if not isinstance(day_text, str) or not isinstance(kind, str) or not 1 <= len(kind) <= 32:
            raise ValueError("Invalid workout fields")
        workout_day = date.fromisoformat(day_text)
        if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ -_" for c in kind):
            raise ValueError("Invalid workout type")
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not 0 <= minutes <= 1440:
            raise ValueError("Invalid duration")
        if isinstance(distance, bool) or not isinstance(distance, (int, float)) or not 0 <= distance <= 1000:
            raise ValueError("Invalid distance")
        if not (float("-inf") < float(minutes) < float("inf") and float("-inf") < float(distance) < float("inf")):
            raise ValueError("Nonfinite measurement")
        if start <= workout_day <= reference:
            weekly.append({"date": workout_day.isoformat(), "type": kind, "duration_minutes": minutes, "distance_km": distance})
            totals["sessions"] += 1
            totals["minutes"] += minutes
            totals["distance_km"] += distance
    weekly.sort(key=lambda item: item["date"], reverse=True)
    return {"available": True, "configured": True, "source": "manual_export",
            "period_start": start.isoformat(), "period_end": reference.isoformat(),
            "summary": {"sessions": totals["sessions"], "duration_minutes": round(totals["minutes"], 1),
                        "distance_km": round(totals["distance_km"], 2)},
            "recent": weekly[:5], "stale": False}


def fitness() -> dict:
    location = os.environ.get("TRIS_FITNESS_FILE", "").strip()
    if not location:
        return {"available": False, "configured": False, "stale": False}
    try:
        return load_fitness(Path(location).expanduser())
    except (OSError, ValueError, TypeError):
        return {"available": False, "configured": True, "stale": True}
