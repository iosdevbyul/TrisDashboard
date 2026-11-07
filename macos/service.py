"""Manage a per-user launchd service for the MacBook dashboard.

This tool never changes power settings or opens firewall/router ports.
"""
import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path

LABEL = "ai.tris.dashboard"
PORT = 8080


def agent_path(home: Path) -> Path:
    return home / "Library" / "LaunchAgents" / (LABEL + ".plist")


def service_config(project: Path, home: Path, lan: bool = False) -> dict:
    python = project / ".venv" / "bin" / "python"
    log_dir = home / "Library" / "Logs" / "TrisDashboard"
    return {
        "Label": LABEL,
        "ProgramArguments": [
            str(python), "-m", "uvicorn", "backend.app:app",
            "--host", "0.0.0.0" if lan else "127.0.0.1",
            "--port", str(PORT),
        ],
        "WorkingDirectory": str(project),
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "StandardOutPath": str(log_dir / "server.log"),
        "StandardErrorPath": str(log_dir / "error.log"),
    }


def run_launchctl(*arguments: str) -> None:
    subprocess.run(["launchctl", *arguments], check=True)


def require_macos() -> None:
    if sys.platform != "darwin":
        raise RuntimeError("Service management requires macOS")
    if os.geteuid() == 0:
        raise RuntimeError("Run as your regular macOS user, not sudo")


def install(project: Path, home: Path, lan: bool) -> None:
    require_macos()
    python = project / ".venv" / "bin" / "python"
    if not python.is_file():
        raise RuntimeError("Create .venv and install requirements first")
    path = agent_path(home)
    if path.exists():
        raise RuntimeError("Already installed. Run uninstall before reinstalling.")
    path.parent.mkdir(parents=True, exist_ok=True)
    (home / "Library" / "Logs" / "TrisDashboard").mkdir(parents=True, exist_ok=True)
    path.write_bytes(plistlib.dumps(service_config(project, home, lan)))
    try:
        run_launchctl("bootstrap", "gui/" + str(os.getuid()), str(path))
    except Exception:
        path.unlink()
        raise
    print("Installed " + LABEL + " (LAN access " + ("enabled" if lan else "disabled") + ")")


def uninstall(home: Path) -> None:
    require_macos()
    path = agent_path(home)
    if not path.exists():
        print("Service is not installed")
        return
    run_launchctl("bootout", "gui/" + str(os.getuid()), str(path))
    path.unlink()
    print("Uninstalled " + LABEL)


def status() -> None:
    require_macos()
    run_launchctl("print", "gui/" + str(os.getuid()) + "/" + LABEL)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage TrisDashboard as a macOS user agent")
    parser.add_argument("command", choices=("install", "uninstall", "status"))
    parser.add_argument("--lan", action="store_true", help="Explicitly expose port 8080 to trusted Wi-Fi")
    args = parser.parse_args()
    project = Path(__file__).resolve().parent.parent
    home = Path.home()
    if args.lan and args.command != "install":
        parser.error("--lan is only valid during install")
    try:
        if args.command == "install":
            install(project, home, args.lan)
        elif args.command == "uninstall":
            uninstall(home)
        else:
            status()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, "Error: " + str(error) + "\n")


if __name__ == "__main__":
    main()
