"""Opt-in per-user macOS LaunchAgent for shared WakTrainer workout files."""
import argparse
import json
import os
import plistlib
import stat
import subprocess
import sys
from pathlib import Path

from macos.periodic_workout import safe_path, require_macos
from macos.receive_workouts import receive, PREFIX, MAX_FILES

LABEL = "ai.tris.dashboard.waktrainer-inbox"
INTERVAL_SECONDS = 900


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


def agent_config(project: Path, home: Path, directory: Path, output: Path) -> dict:
    return {
        "Label": LABEL,
        "ProgramArguments": [
            str(project / ".venv" / "bin" / "python"), "-m",
            "macos.periodic_inbox", "run-once", "--directory",
            str(directory), "--output", str(output),
        ],
        "WorkingDirectory": str(project),
        "RunAtLoad": True,
        "StartInterval": INTERVAL_SECONDS,
        "StandardOutPath": str(home / "Library" / "Logs" / "TrisDashboard" / "inbox.log"),
        "StandardErrorPath": str(home / "Library" / "Logs" / "TrisDashboard" / "inbox-error.log"),
    }


def install(project: Path, home: Path, directory: Path, output: Path) -> None:
    require_macos()
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
    agent.write_bytes(plistlib.dumps(agent_config(project, home, directory, output)))
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
              "over_file_limit": False, "output_configured": False}
    if not agent.is_file() or agent.is_symlink() or agent.stat().st_size > 16 * 1024:
        return result
    result["installed"] = True
    try:
        payload = plistlib.loads(agent.read_bytes())
        arguments = payload["ProgramArguments"]
        if (not isinstance(arguments, list) or len(arguments) != 8
                or arguments[1:4] != ["-m", "macos.periodic_inbox", "run-once"]
                or arguments[4] != "--directory" or arguments[6] != "--output"
                or not isinstance(arguments[5], str)
                or not isinstance(arguments[7], str)):
            return result
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
    args = parser.parse_args()
    try:
        project, home = Path(__file__).resolve().parent.parent, Path.home()
        if args.command == "status":
            if args.directory or args.output:
                raise ValueError("Status has no file arguments")
            print(json.dumps(inspect(home), sort_keys=True))
        elif args.command == "uninstall":
            if args.directory or args.output:
                raise ValueError("Uninstall has no file arguments")
            uninstall(home)
        else:
            if args.directory is None or args.output is None:
                raise ValueError("Inbox directory and output are required")
            directory, output = private_inbox(args.directory), safe_path(args.output)
            if args.command == "install":
                install(project, home, directory, output)
            else:
                # Runs only after explicit install or user invocation; no iPhone polling.
                receive(directory, output, apply=True)
    except (OSError, ValueError, RuntimeError, TypeError, subprocess.CalledProcessError):
        parser.exit(1, "Inbox scheduler failed: check permissions and private paths.\n")


if __name__ == "__main__":
    main()
