"""Read-only MacBook operations status: no private values or external API calls."""
import argparse
import json
from pathlib import Path

from macos.doctor import inspect as inspect_mac
from macos.preflight import inspect_settings
from macos.periodic_inbox import inspect as inspect_inbox


def readiness(project: Path, home: Path, *, settings: Path | None = None,
              mac_check=inspect_mac, settings_check=inspect_settings,
              inbox_check=inspect_inbox) -> dict:
    host = mac_check(project, home)
    import_status = inbox_check(home)
    result = {
        "mac": host,
        "workout_inbox": import_status,
        "settings": {"checked": settings is not None},
    }
    if settings is not None:
        checked = settings_check(settings)
        result["settings"] = {
            "checked": True,
            "valid": checked["settings"] == "valid",
            "private_files_ready": checked["ready"],
            "file_states": checked["files"],
        }
    result["summary"] = {
        "python_ready": bool(host.get("python_supported")),
        "server_reachable": bool(host.get("local_server_reachable")),
        "settings_ready": (settings is None or result["settings"].get("private_files_ready") is True),
        "inbox_agent_installed": bool(import_status.get("installed")),
        "inbox_last_run_known": bool(import_status.get("last_run_known")),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Privacy-safe MacBook dashboard readiness check")
    parser.add_argument("--settings", type=Path, help="Optional private settings file to validate")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    project = Path(__file__).resolve().parent.parent
    result = readiness(project, Path.home(), settings=args.settings)
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print("Mac Python ready: " + str(result["summary"]["python_ready"]))
        print("Dashboard server reachable: " + str(result["summary"]["server_reachable"]))
        print("Configured private files ready: " + str(result["summary"]["settings_ready"]))
        print("Workout inbox agent installed: " + str(result["summary"]["inbox_agent_installed"]))
        print("Workout inbox last run known: " + str(result["summary"]["inbox_last_run_known"]))
        print("This check never contacts external data providers or modifies settings.")
    if not result["summary"]["python_ready"] or not result["summary"]["settings_ready"]:
        parser.exit(1)


if __name__ == "__main__":
    main()
