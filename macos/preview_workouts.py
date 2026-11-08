"""Read-only preview for user-transferred WakTrainer export files."""
import argparse
import json
from pathlib import Path

from backend.fitness import load_fitness
from macos.import_waktrainer import merged_workouts, parse_export


def preview(source: Path, destination: Path) -> dict:
    data = parse_export(source.expanduser().resolve())
    destination = destination.expanduser().resolve()
    existing = []
    if destination.exists():
        load_fitness(destination)
        payload = json.loads(destination.read_text(encoding="utf-8"))
        existing = payload["workouts"]
    combined, added = merged_workouts(existing, data["workouts"])
    dates = [workout["date"] for workout in combined]
    return {
        "existing": len(existing),
        "incoming": len(data["workouts"]),
        "new": added,
        "duplicates": len(data["workouts"]) - added,
        "total": len(combined),
        "earliest_day": min(dates) if dates else None,
        "latest_day": max(dates) if dates else None,
        "written": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a private workout import without modifying any files")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = preview(args.input, args.output)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        parser.exit(1, "Preview failed: validate the workout export and destination.\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
