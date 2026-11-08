"""Opt-in macOS scheduled local workout export import (no mobile sync)."""
import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path

from macos.import_waktrainer import import_export

LABEL = "ai.tris.dashboard.workout-import"
INTERVAL_SECONDS = 900


def agent_path(home: Path) -> Path:
    return home / "Library" / "LaunchAgents" / (LABEL + ".plist")


def safe_path(value: Path) -> Path:
    resolved = value.expanduser().resolve()
    project = Path(__file__).resolve().parent.parent
    if project == resolved or project in resolved.parents:
        raise ValueError("Workout imports must use private files outside the repository")
    if resolved.suffix.lower() != ".json":
        raise ValueError("Workout imports need JSON files")
    return resolved


def import_once(source: Path, output: Path) -> dict:
    if not source.is_file():
        return {"state": "waiting-for-export", "added": 0}
    # Let the importer decide existence while holding its file lock.
    result = import_export(source, output, merge=True)
    return {"state": "imported", "added": result["added"]}


def agent_config(project: Path, home: Path, source: Path, output: Path) -> dict:
    python = project / ".venv" / "bin" / "python"
    log_dir = home / "Library" / "Logs" / "TrisDashboard"
    return {
        "Label": LABEL,
        "ProgramArguments": [str(python), "-m", "macos.periodic_workout",
                             "run-once", "--input", str(source), "--output", str(output)],
        "WorkingDirectory": str(project),
        "RunAtLoad": True,
        "StartInterval": INTERVAL_SECONDS,
        "StandardOutPath": str(log_dir / "workout-import.log"),
        "StandardErrorPath": str(log_dir / "workout-import-error.log"),
    }


def require_macos() -> None:
    if sys.platform != "darwin" or os.geteuid() == 0:
        raise RuntimeError("Run as a regular logged-in macOS user")


def install(project: Path, home: Path, source: Path, output: Path) -> None:
    require_macos()
    python = project / ".venv" / "bin" / "python"
    if not python.is_file():
        raise RuntimeError("Create .venv first")
    source, output = safe_path(source), safe_path(output)
    if source == output:
        raise ValueError("Source and output must differ")
    agent = agent_path(home)
    if agent.exists():
        raise RuntimeError("Workout import agent already installed")
    agent.parent.mkdir(parents=True, exist_ok=True)
    (home / "Library" / "Logs" / "TrisDashboard").mkdir(parents=True, exist_ok=True)
    agent.write_bytes(plistlib.dumps(agent_config(project, home, source, output)))
    try:
        subprocess.run(["launchctl", "bootstrap", "gui/" + str(os.getuid()), str(agent)], check=True)
    except Exception:
        agent.unlink()
        raise


def uninstall(home: Path) -> None:
    require_macos()
    agent = agent_path(home)
    if agent.is_file():
        subprocess.run(["launchctl", "bootout", "gui/" + str(os.getuid()), str(agent)], check=True)
        agent.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Optional private local WakTrainer import schedule")
    parser.add_argument("command", choices=("install", "uninstall", "run-once"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        home = Path.home()
        project = Path(__file__).resolve().parent.parent
        if args.command == "uninstall":
            if args.input or args.output:
                raise ValueError("Uninstall does not accept file paths")
            uninstall(home)
        else:
            if args.input is None or args.output is None:
                raise ValueError("Input and output are required")
            source, output = safe_path(args.input), safe_path(args.output)
            if source == output:
                raise ValueError("Source and output must differ")
            if args.command == "install":
                install(project, home, source, output)
            else:
                import_once(source, output)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError):
        parser.exit(1, "Workout import failed. Check local paths and permissions.\n")


if __name__ == "__main__":
    main()
