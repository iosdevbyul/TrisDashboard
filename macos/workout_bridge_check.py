"""Offline v2 export -> Mac inbox -> dashboard fitness contract acceptance test."""
import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.fitness import load_fitness
from macos.preview_workouts import preview
from macos.receive_workouts import receive


def check_bridge() -> dict:
    """Synthetic data only. Never read real user files or send network requests."""
    started = datetime.now(timezone.utc).replace(microsecond=0)
    expected_day = started.astimezone(ZoneInfo("Asia/Seoul")).date()
    session = {
        "session_id": "synthetic-dashboard-bridge-001",
        "started_at": started.isoformat(),
        "activity_type": "running",
        "duration_seconds": 1800,
        "distance_meters": 5000,
    }
    with tempfile.TemporaryDirectory(prefix="tris-workout-check-") as directory:
        root = Path(directory)
        inbox = root / "Downloads"
        inbox.mkdir()
        target = root / "private" / "fitness.json"
        for filename in ("waktrainer-dashboard-first.json", "waktrainer-dashboard-second.json"):
            (inbox / filename).write_text(json.dumps({
                "schema_version": 2, "sessions": [session],
            }), encoding="utf-8")
        source = inbox / "waktrainer-dashboard-first.json"
        before = preview(source, target, timezone_name="Asia/Seoul")
        dry = receive(inbox, target, timezone_name="Asia/Seoul")
        if target.exists() or before["new"] != 1 or dry["new"] != 1:
            raise ValueError("Preview unexpectedly modified output or failed contract")
        imported = receive(inbox, target, apply=True, timezone_name="Asia/Seoul")
        if not imported["written"] or imported["new"] != 1 or imported["duplicates"] != 1:
            raise ValueError("Overlapping export merge contract failed")
        data = load_fitness(target, today=expected_day)
        if (not data["available"] or data["summary"]["sessions"] != 1
                or data["summary"]["distance_km"] != 5.0
                or data["stable_id_count"] != 1):
            raise ValueError("Dashboard workout summary contract failed")
        stored = json.loads(target.read_text(encoding="utf-8"))["workouts"]
        if (len(stored) != 1 or stored[0]["date"] != expected_day.isoformat()
                or stored[0]["session_id"] != session["session_id"]):
            raise ValueError("Workout timezone or stable identity contract failed")
        repeated = receive(inbox, target, apply=True, timezone_name="Asia/Seoul")
        if repeated["written"] or repeated["new"] != 0:
            raise ValueError("Idempotent repeat import contract failed")
    return {
        "passed": True, "schema_version": 2,
        "source_files": 2, "unique_sessions": 1,
        "duplicate_sessions_skipped": 1, "repeat_import_safe": True,
        "timezone_verified": True, "private_files_used": False,
        "network_requests": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline synthetic WakTrainer-to-dashboard acceptance")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = check_bridge()
    except (OSError, ValueError, TypeError, KeyError):
        parser.exit(1, "Synthetic workout bridge contract failed.\n")
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print("Synthetic WakTrainer export to TrisDashboard: passed")
        print("No actual user files or external APIs were accessed.")


if __name__ == "__main__":
    main()
