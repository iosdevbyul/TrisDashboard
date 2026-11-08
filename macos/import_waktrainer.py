"""Versioned opt-in WakTrainer export bridge. Does not access the WakTrainer app."""
import argparse
import fcntl
import json
import math
import os
import stat
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def validated_timezone(name: str | None):
    if name is None:
        return None
    if not isinstance(name, str) or not name or len(name) > 100:
        raise ValueError("Invalid workout timezone")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("Unsupported workout timezone") from error

from backend.fitness import load_fitness

# Duplicate signature uses the fields available in the v1 interchange contract.
# Distinct sessions with identical values are indistinguishable in v1.
def workout_key(item: dict) -> tuple:
    if item.get("session_id"):
        return ("id", item["session_id"])
    return ("legacy", item["date"], item["type"], item["duration_minutes"],
            item.get("distance_km", 0))


def merged_workouts(existing: list, incoming: list) -> tuple[list, int]:
    combined = list(existing)
    known = {}
    for item in existing:
        signature = workout_key(item)
        if signature in known and known[signature] != item:
            raise ValueError("Conflicting existing workout session ID")
        known[signature] = item
    added = 0
    for item in incoming:
        signature = workout_key(item)
        if signature in known:
            if known[signature] != item:
                raise ValueError("Conflicting workout session ID; import stopped")
            continue
        combined.append(item)
        known[signature] = item
        added += 1
    if len(combined) > MAX_SESSIONS:
        raise ValueError("Too many combined sessions")
    return combined, added

TYPES = {
    "running": "Running",
    "walking": "Walking",
    "cycling": "Cycling",
    "strength": "Strength",
    "climbing": "Climbing",
}
MAX_BYTES = 128 * 1024
MAX_SESSIONS = 500


def _unique_export_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate workout export JSON key")
        result[key] = value
    return result


def _reject_export_constant(value):
    raise ValueError("Non-standard workout export JSON value")


def parse_export(path: Path, *, timezone_name: str | None = None,
                 raw: bytes | None = None) -> dict:
    if raw is None:
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("Export is too large")
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Export is too large")
    export = json.loads(raw,
                        object_pairs_hook=_unique_export_keys,
                        parse_constant=_reject_export_constant)
    if not isinstance(export, dict) or type(export.get("schema_version")) is not int or export["schema_version"] not in (1, 2):
        raise ValueError("Unsupported export version")
    version = export["schema_version"]
    sessions = export.get("sessions")
    if not isinstance(sessions, list) or len(sessions) > MAX_SESSIONS:
        raise ValueError("Invalid sessions")
    zone = validated_timezone(timezone_name)
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
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("Workout time requires a timezone")
        if timestamp.astimezone(timezone.utc) > datetime.now(timezone.utc) + timedelta(minutes=10):
            raise ValueError("Future workout session is not allowed")
        if (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
                or isinstance(meters, bool) or not isinstance(meters, (int, float))
                or not math.isfinite(seconds) or not math.isfinite(meters)
                or not 0 <= seconds <= 86400 or not 0 <= meters <= 1_000_000):
            raise ValueError("Invalid session measurement")
        workout = {
            "date": (timestamp.astimezone(zone) if zone else timestamp).date().isoformat(),
            "type": TYPES[kind],
            "duration_minutes": round(seconds / 60, 3),
            "distance_km": round(meters / 1000, 3),
        }
        if version == 2:
            session_id = session.get("session_id")
            if (not isinstance(session_id, str) or not 1 <= len(session_id) <= 100
                    or not all(char in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_:." for char in session_id)):
                raise ValueError("Version 2 requires stable session_id")
            workout["session_id"] = session_id
        workouts.append(workout)
    if version == 2 and len({item["session_id"] for item in workouts}) != len(workouts):
        raise ValueError("Duplicate session_id in export")
    if version == 1 and len({workout_key(item) for item in workouts}) != len(workouts):
        raise ValueError("Duplicate legacy workout in export")
    return {"workouts": workouts}


def _import_export_unlocked(source: Path, destination: Path, *, force: bool = False,
                           dry_run: bool = False, merge: bool = False,
                           timezone_name: str | None = None) -> dict:
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    project = Path(__file__).resolve().parent.parent
    if (source == destination or destination == project
            or project in destination.parents or destination.suffix.lower() != ".json"):
        raise ValueError("Destination must be private JSON outside repository")
    data = parse_export(source, timezone_name=timezone_name)
    if force and merge:
        raise ValueError("--force and --merge cannot be combined")
    added = len(data["workouts"])
    if destination.exists():
        if merge:
            # Validate existing data before considering an append.
            load_fitness(destination)
            old = json.loads(destination.read_text(encoding="utf-8"))
            if not isinstance(old, dict) or not isinstance(old.get("workouts"), list):
                raise ValueError("Existing workout file is invalid")
            merged, added = merged_workouts(old["workouts"], data["workouts"])
            data["workouts"] = merged
            if added == 0:
                # Preserve existing bytes, inode and modification date on repeated scheduled imports.
                return {"sessions": len(merged), "added": 0, "written": False}
        elif not force:
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
        # Evaluate local workout days in the same timezone used for export conversion.
        zone = validated_timezone(timezone_name)
        validation_day = datetime.now(zone).date() if zone else None
        load_fitness(temp, today=validation_day)
        if not dry_run:
            os.replace(temp, destination)
            temp = None
        return {"sessions": len(data["workouts"]), "added": added, "written": not dry_run}
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def import_export(source: Path, destination: Path, *, force: bool = False,
                  dry_run: bool = False, merge: bool = False,
                  timezone_name: str | None = None) -> dict:
    """Serialize imports from the MacBook's scheduled and manual paths."""
    destination = destination.expanduser().resolve()
    project = Path(__file__).resolve().parent.parent
    if (destination == project or project in destination.parents
            or destination.suffix.lower() != ".json"):
        raise ValueError("Destination must be private JSON outside repository")
    if force and merge:
        raise ValueError("--force and --merge cannot be combined")
    if dry_run:
        # Validation should not create destination folders, lock files or JSON output.
        return _import_export_unlocked(
            source, destination, force=force, dry_run=True, merge=merge,
            timezone_name=timezone_name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Persistent sidecar lock is intentionally never unlinked: removing it races waiting writers.
    lock_path = destination.with_name(destination.name + ".lock")
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(lock_path, flags, 0o600)
    with os.fdopen(fd, "a+b") as lock_file:
        info = os.fstat(lock_file.fileno())
        if (not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_mode & 0o077):
            raise ValueError("Workout lock must be owner-only regular file")
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            return _import_export_unlocked(
                source, destination, force=force, dry_run=False, merge=merge,
                timezone_name=timezone_name)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a versioned WakTrainer JSON export")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--merge", action="store_true",
                        help="Append unique sessions without replacing existing workout history")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timezone", dest="timezone_name",
                        help="Optional IANA timezone for workout calendar dates (e.g. Asia/Seoul)")
    args = parser.parse_args()
    try:
        result = import_export(args.input, args.output, force=args.force,
                               dry_run=args.dry_run, merge=args.merge,
                               timezone_name=args.timezone_name)
    except (OSError, ValueError, TypeError, KeyError):
        parser.exit(1, "Import failed: invalid WakTrainer export or destination.\n")
    print("Validated " + str(result["sessions"]) + " sessions (" + str(result["added"]) + " new)" +
          ("; saved locally" if result["written"] else "; dry-run only"))


if __name__ == "__main__":
    main()
