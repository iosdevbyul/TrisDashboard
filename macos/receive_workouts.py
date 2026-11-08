"""Opt-in import of WakTrainer v2 JSON files shared to a Mac inbox."""
import argparse
import json
import os
import stat
import tempfile
from pathlib import Path

from backend.fitness import load_fitness
from macos.import_waktrainer import (
    MAX_SESSIONS, import_export, merged_workouts, parse_export,
)

PREFIX = "waktrainer-dashboard-"
MAX_FILES = 50


def receive(directory: Path, output: Path, *, apply: bool = False) -> dict:
    directory = directory.expanduser().resolve()
    output = output.expanduser().resolve()
    if not directory.is_dir():
        raise ValueError("Workout inbox directory is missing")
    candidates = sorted(directory.glob(PREFIX + "*.json"), key=lambda item: item.name)
    if len(candidates) > MAX_FILES:
        raise ValueError("Too many exported files in inbox")

    sessions = []
    records = []
    for path in candidates:
        if path.is_symlink() or not path.is_file():
            raise ValueError("Unsafe workout export file")
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError("Workout export is not owned by the current user")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or type(payload.get("schema_version")) is not int or payload["schema_version"] != 2:
            raise ValueError("Inbox accepts only WakTrainer version 2 exports")
        validated = parse_export(path)["workouts"]
        sessions.extend(payload["sessions"])
        records.extend(validated)
        if len(sessions) > MAX_SESSIONS:
            raise ValueError("Too many workouts to import")

    # Reject conflicts between separate incoming exports before changing history.
    _, _ = merged_workouts([], records)
    existing = []
    if output.exists():
        load_fitness(output)
        previous = json.loads(output.read_text(encoding="utf-8"))
        existing = previous["workouts"]
    combined, added = merged_workouts(existing, records)
    summary = {
        "files": len(candidates), "incoming": len(records),
        "existing": len(existing), "new": added,
        "duplicates": len(records) - added,
        "total": len(combined), "written": False,
    }
    if not apply or added == 0:
        return summary

    # Stage a single bounded import; import_export owns its sidecar lock and
    # atomically writes only when every source and session has validated.
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json",
            prefix=".tris-inbox-", dir=output.parent, delete=False
        ) as handle:
            staged = Path(handle.name)
            json.dump({"schema_version": 2, "sessions": sessions}, handle)
        result = import_export(staged, output, merge=True)
        summary["written"] = result["written"]
        return summary
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview/import WakTrainer AirDrop or Files exports")
    parser.add_argument("--directory", type=Path, required=True, help="Mac inbox for shared JSON files")
    parser.add_argument("--output", type=Path, required=True, help="Private dashboard fitness JSON")
    parser.add_argument("--apply", action="store_true", help="Validate and merge into output; otherwise preview only")
    args = parser.parse_args()
    try:
        report = receive(args.directory, args.output, apply=args.apply)
    except (OSError, ValueError, TypeError, KeyError):
        parser.exit(1, "Workout inbox validation failed; existing history was not intentionally replaced.\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
