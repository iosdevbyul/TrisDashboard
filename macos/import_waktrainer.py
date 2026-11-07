"""Versioned opt-in WakTrainer export bridge. Does not access the WakTrainer app."""
import argparse
import json
import math
import os
import tempfile
from datetime import datetime
from pathlib import Path

from backend.fitness import load_fitness

TYPES = {
    "running": "Running",
    "walking": "Walking",
    "cycling": "Cycling",
    "strength": "Strength",
    "climbing": "Climbing",
}
MAX_BYTES = 128 * 1024
MAX_SESSIONS = 500


def parse_export(path: Path) -> dict:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Export is too large")
    export = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(export, dict) or export.get("schema_version") != 1:
        raise ValueError("Unsupported export version")
    sessions = export.get("sessions")
    if not isinstance(sessions, list) or len(sessions) > MAX_SESSIONS:
        raise ValueError("Invalid sessions")
    workouts = []
    for session in sessions:
        if not isinstance(session, dict):
            raise ValueError("Invalid session")
        started = session.get("started_at")
        kind = session.get("activity_type")
        seconds = session.get("duration_seconds")
        meters = session.get("distance_meters", 0)
        if not isinstance(started, str) or kind not in TYPES:
            raise ValueError("Invalid activity or time")
        timestamp = datetime.fromisoformat(started.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("Workout time requires a timezone")
        if (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
                or isinstance(meters, bool) or not isinstance(meters, (int, float))
                or not math.isfinite(seconds) or not math.isfinite(meters)
                or not 0 <= seconds <= 86400 or not 0 <= meters <= 1_000_000):
            raise ValueError("Invalid session measurement")
        workouts.append({
            "date": timestamp.date().isoformat(),
            "type": TYPES[kind],
            "duration_minutes": round(seconds / 60, 3),
            "distance_km": round(meters / 1000, 3),
        })
    return {"workouts": workouts}


def import_export(source: Path, destination: Path, *, force: bool = False,
                  dry_run: bool = False) -> dict:
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    project = Path(__file__).resolve().parent.parent
    if (source == destination or destination == project
            or project in destination.parents or destination.suffix.lower() != ".json"):
        raise ValueError("Destination must be private JSON outside repository")
    data = parse_export(source)
    if destination.exists() and not force:
        raise ValueError("Destination exists")
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json",
                                         prefix=".tris-waktrainer-",
                                         dir=None if dry_run else destination.parent,
                                         delete=False) as handle:
            temp = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False)
        load_fitness(temp)
        if not dry_run:
            os.replace(temp, destination)
            temp = None
        return {"sessions": len(data["workouts"]), "written": not dry_run}
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a versioned WakTrainer JSON export")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = import_export(args.input, args.output, force=args.force,
                               dry_run=args.dry_run)
    except (OSError, ValueError, TypeError, KeyError):
        parser.exit(1, "Import failed: invalid WakTrainer export or destination.\n")
    print("Validated " + str(result["sessions"]) + " sessions" +
          ("; saved locally" if result["written"] else "; dry-run only"))


if __name__ == "__main__":
    main()
