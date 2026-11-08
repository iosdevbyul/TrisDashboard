"""Opt-in per-user macOS LaunchAgent for shared WakTrainer workout files."""
import argparse
import json
import tempfile
from datetime import datetime, timezone
import os
import plistlib
from macos.agent_files import write_private_agent
import stat
import subprocess
import sys
from pathlib import Path

from macos.periodic_workout import safe_path, require_macos
from macos.receive_workouts import receive, PREFIX, MAX_FILES
from macos.import_waktrainer import validated_timezone

LABEL = "ai.tris.dashboard.waktrainer-inbox"
INTERVAL_SECONDS = 900


def state_path(home: Path) -> Path:
    return home / "Library" / "Logs" / "TrisDashboard" / "inbox-status.json"


def write_run_state(home: Path, *, success: bool, files: int = 0, added: int = 0) -> None:
    """Store only a timestamp and aggregate counts, never source paths or errors."""
    destination = state_path(home)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", prefix=".tris-inbox-status-",
            suffix=".json", dir=destination.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump({
                "checked_at_utc": datetime.now(timezone.utc).isoformat(),
                "success": success,
                "candidate_files": files if success else None,
                "new_workouts": added if success else None,
            }, stream)
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_run_state(home: Path) -> dict:
    path = state_path(home)
    if path.is_symlink():
        return {"last_run_known": False}
    try:
        if not path.is_file() or path.stat().st_size > 2048:
            return {"last_run_known": False}
        data = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or type(data.get("success")) is not bool
                or not isinstance(data.get("checked_at_utc"), str)):
            return {"last_run_known": False}
        stamp = datetime.fromisoformat(data["checked_at_utc"])
        if stamp.tzinfo is None:
            return {"last_run_known": False}
        # Reject a corrupt or forged future success timestamp; the strict
        # readiness gate must not trust a report whose clock is far ahead.
        if (stamp - datetime.now(timezone.utc)).total_seconds() > 300:
            return {"last_run_known": False}
        added = data.get("new_workouts")
        if data["success"] and (type(added) is not int or not 0 <= added <= 500):
            return {"last_run_known": False}
        return {"last_run_known": True,
                "last_run_success": data["success"],
                "last_run_utc": data["checked_at_utc"],
                "last_new_workouts": added if data["success"] else None}
    except (OSError, ValueError, TypeError):
        return {"last_run_known": False}



def agent_path(home: Path) -> Path:
    return home / "Library" / "LaunchAgents" / (LABEL + ".plist")


def private_inbox(value: Path) -> Path:
    value = value.expanduser()
    if value.is_symlink():
        raise ValueError("Inbox must not be a symlink")
    resolved = value.resolve()
    repo = Path(__file__).resolve().parent.parent
    if resolved == repo or repo in resolved.parents:
        raise ValueError("Inbox must live outside the public repository")
    info = resolved.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError("Inbox must be an owned directory")
    return resolved


def agent_config(project: Path, home: Path, directory: Path, output: Path,
                 timezone_name: str | None = None) -> dict:
    validated_timezone(timezone_name)
    return {
        "Label": LABEL,
        "ProgramArguments": [
            str(project / ".venv" / "bin" / "python"), "-m",
            "macos.periodic_inbox", "run-once", "--directory",
            str(directory), "--output", str(output),
        ] + (["--timezone", timezone_name] if timezone_name is not None else []),
        "WorkingDirectory": str(project),
        "RunAtLoad": True,
        "StartInterval": INTERVAL_SECONDS,
        "StandardOutPath": str(home / "Library" / "Logs" / "TrisDashboard" / "inbox.log"),
        "StandardErrorPath": str(home / "Library" / "Logs" / "TrisDashboard" / "inbox-error.log"),
    }


def install(project: Path, home: Path, directory: Path, output: Path,
            timezone_name: str | None = None) -> None:
    require_macos()
    validated_timezone(timezone_name)
    directory = private_inbox(directory)
    output = safe_path(output)
    if output.parent == directory and output.name.startswith("waktrainer-dashboard-"):
        raise ValueError("Output must not resemble an incoming export file")
    if not (project / ".venv" / "bin" / "python").is_file():
        raise RuntimeError("Create the project virtual environment first")
    agent = agent_path(home)
    if agent.exists():
        raise ValueError("Inbox LaunchAgent already installed")
    agent.parent.mkdir(parents=True, exist_ok=True)
    (home / "Library" / "Logs" / "TrisDashboard").mkdir(parents=True, exist_ok=True)
    write_private_agent(agent, agent_config(project, home, directory, output, timezone_name=timezone_name))
    try:
        subprocess.run(["launchctl", "bootstrap", "gui/" + str(os.getuid()), str(agent)], check=True)
    except Exception:
        agent.unlink(missing_ok=True)
        raise


def uninstall(home: Path) -> None:
    require_macos()
    agent = agent_path(home)
    if agent.is_file():
        subprocess.run(["launchctl", "bootout", "gui/" + str(os.getuid()), str(agent)], check=True)
        agent.unlink()


def inspect(home: Path) -> dict:
    """Report readiness without exposing file names, paths or workout data."""
    agent = agent_path(home)
    result = {"installed": False, "configuration_valid": False,
              "inbox_available": False, "candidate_files": 0,
              "over_file_limit": False, "output_configured": False,
              "timezone_configured": False,
              **read_run_state(home)}
    if not agent.is_file() or agent.is_symlink() or agent.stat().st_size > 16 * 1024:
        return result
    result["installed"] = True
    try:
        payload = plistlib.loads(agent.read_bytes())
        arguments = payload["ProgramArguments"]
        if (not isinstance(payload, dict) or payload.get("Label") != LABEL
                or payload.get("RunAtLoad") is not True
                or type(payload.get("StartInterval")) is not int
                or payload["StartInterval"] != INTERVAL_SECONDS
                or not isinstance(payload.get("WorkingDirectory"), str)
                or not isinstance(arguments, list) or len(arguments) not in (8, 10)
                or arguments[1:4] != ["-m", "macos.periodic_inbox", "run-once"]
                or arguments[4] != "--directory" or arguments[6] != "--output"
                or not isinstance(arguments[0], str)
                or not Path(arguments[0]).is_absolute()
                or not arguments[0].endswith("/.venv/bin/python")
                or not Path(payload["WorkingDirectory"]).is_absolute()
                or str(Path(payload["WorkingDirectory"]) / ".venv" / "bin" / "python") != arguments[0]
                or not isinstance(arguments[5], str)
                or not isinstance(arguments[7], str)):
            return result
        if len(arguments) == 10:
            if arguments[8] != "--timezone" or not isinstance(arguments[9], str):
                return result
            validated_timezone(arguments[9])
            result["timezone_configured"] = True
        directory = private_inbox(Path(arguments[5]))
        output = safe_path(Path(arguments[7]))
        if output.parent == directory and output.name.startswith(PREFIX):
            return result
        result["configuration_valid"] = True
        result["inbox_available"] = True
        result["output_configured"] = True
        candidates = list(directory.glob(PREFIX + "*.json"))
        result["candidate_files"] = len(candidates)
        result["over_file_limit"] = len(candidates) > MAX_FILES
    except (OSError, ValueError, KeyError, TypeError, plistlib.InvalidFileException):
        return result
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Optional local WakTrainer AirDrop inbox scheduler")
    parser.add_argument("command", choices=("install", "uninstall", "run-once", "status"))
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timezone", dest="timezone_name",
                        help="IANA calendar timezone for UTC WakTrainer exports")
    args = parser.parse_args()
    try:
        project, home = Path(__file__).resolve().parent.parent, Path.home()
        if args.command == "status":
            if args.directory or args.output or args.timezone_name:
                raise ValueError("Status has no file arguments")
            print(json.dumps(inspect(home), sort_keys=True))
        elif args.command == "uninstall":
            if args.directory or args.output or args.timezone_name:
                raise ValueError("Uninstall has no file arguments")
            uninstall(home)
        else:
            if args.directory is None or args.output is None:
                raise ValueError("Inbox directory and output are required")
            directory, output = private_inbox(args.directory), safe_path(args.output)
            validated_timezone(args.timezone_name)
            if args.command == "install":
                install(project, home, directory, output,
                        timezone_name=args.timezone_name)
            else:
                # Runs only after explicit install or user invocation; no iPhone polling.
                try:
                    summary = receive(directory, output, apply=True,
                                      timezone_name=args.timezone_name)
                except (OSError, ValueError, TypeError, KeyError):
                    write_run_state(home, success=False)
                    raise
                else:
                    write_run_state(home, success=True,
                                    files=summary["files"], added=summary["new"])
    except (OSError, ValueError, RuntimeError, TypeError, subprocess.CalledProcessError):
        parser.exit(1, "Inbox scheduler failed: check permissions and private paths.\n")


if __name__ == "__main__":
    main()
