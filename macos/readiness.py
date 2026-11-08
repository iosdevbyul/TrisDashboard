"""Read-only MacBook operations status: no private values or external API calls."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from macos.doctor import inspect as inspect_mac
from macos.preflight import inspect_settings
from macos.periodic_inbox import inspect as inspect_inbox


def readiness(project: Path, home: Path, *, settings: Path | None = None,
              require_server: bool = False, require_inbox: bool = False,
              require_recent_inbox: bool = False, now: datetime | None = None,
              mac_check=inspect_mac, settings_check=inspect_settings,
              inbox_check=inspect_inbox) -> dict:
    if now is not None and (not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None):
        raise ValueError("Readiness reference requires a timezone-aware datetime")
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
        "venv_ready": bool(host.get("venv_created")),
        "server_reachable": bool(host.get("local_server_reachable")),
        "settings_ready": (settings is None or result["settings"].get("private_files_ready") is True),
        "inbox_agent_installed": bool(import_status.get("installed")),
        "inbox_last_run_known": bool(import_status.get("last_run_known")),
    }
    failures = []
    if not result["summary"]["python_ready"]:
        failures.append("python")
    if not result["summary"]["venv_ready"]:
        failures.append("venv")
    if settings is not None and not result["summary"]["settings_ready"]:
        failures.append("settings")
    if require_server and not result["summary"]["server_reachable"]:
        failures.append("server")
    if require_inbox or require_recent_inbox:
        if not (import_status.get("installed") and
                import_status.get("configuration_valid") and
                import_status.get("inbox_available") and
                not import_status.get("over_file_limit")):
            failures.append("inbox-configuration")
    if require_recent_inbox:
        latest = import_status.get("last_run_utc")
        recent = False
        if import_status.get("last_run_success") is True and isinstance(latest, str):
            try:
                observed = datetime.fromisoformat(latest)
                if observed.tzinfo is not None:
                    elapsed = ((now or datetime.now(timezone.utc)) - observed).total_seconds()
                    recent = 0 <= elapsed <= 45 * 60
            except (ValueError, TypeError, OverflowError):
                pass
        if not recent:
            failures.append("inbox-last-run")
    result["summary"]["deployment_ready"] = not failures
    result["summary"]["unmet_requirements"] = failures
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Privacy-safe MacBook dashboard readiness check")
    parser.add_argument("--settings", type=Path, help="Optional private settings file to validate")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-server", action="store_true",
                        help="Fail unless the MacBook localhost server responds")
    parser.add_argument("--require-inbox", action="store_true",
                        help="Fail unless the optional workout inbox agent is configured")
    parser.add_argument("--require-recent-inbox", action="store_true",
                        help="Fail unless the workout inbox succeeded within 45 minutes")
    args = parser.parse_args()
    project = Path(__file__).resolve().parent.parent
    result = readiness(project, Path.home(), settings=args.settings,
                       require_server=args.require_server,
                       require_inbox=args.require_inbox,
                       require_recent_inbox=args.require_recent_inbox)
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print("Mac Python ready: " + str(result["summary"]["python_ready"]))
        print("Virtual environment ready: " + str(result["summary"]["venv_ready"]))
        print("Dashboard server reachable: " + str(result["summary"]["server_reachable"]))
        print("Configured private files ready: " + str(result["summary"]["settings_ready"]))
        print("Workout inbox agent installed: " + str(result["summary"]["inbox_agent_installed"]))
        print("Workout inbox last run known: " + str(result["summary"]["inbox_last_run_known"]))
        print("Deployment ready: " + str(result["summary"]["deployment_ready"]))
        if result["summary"]["unmet_requirements"]:
            print("Unmet requirements: " +
                  ", ".join(result["summary"]["unmet_requirements"]))
        print("This check never contacts external data providers or modifies settings.")
    if not result["summary"]["deployment_ready"]:
        parser.exit(1)


if __name__ == "__main__":
    main()
