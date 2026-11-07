"""Manage a per-user launchd service for the MacBook dashboard.

This tool never changes power settings or opens firewall/router ports.
"""
import argparse
import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path

LABEL = "ai.tris.dashboard"
PORT = 8080


def agent_path(home: Path) -> Path:
    return home / "Library" / "LaunchAgents" / (LABEL + ".plist")


ALLOWED_SETTINGS = ("TRIS_LATITUDE", "TRIS_LONGITUDE", "TRIS_LOCATION_NAME", "TRIS_GITHUB_REPOS", "TRIS_PORTFOLIO_FILE", "TRIS_FITNESS_FILE")


def read_public_settings(path: Path) -> dict[str, str]:
    """Explicitly allow public display settings only; never load secrets into launchd plist."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Settings must be a JSON object")
    if any(key not in ALLOWED_SETTINGS for key in data):
        raise ValueError("Unsupported settings key")
    settings = {}
    for key, value in data.items():
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            raise ValueError("Settings values must be strings or numbers")
        settings[key] = str(value)
        if not settings[key] or len(settings[key]) > 300:
            raise ValueError("Settings value outside supported length")
    for key, minimum, maximum in (("TRIS_LATITUDE", -90, 90), ("TRIS_LONGITUDE", -180, 180)):
        if key in settings:
            try:
                number = float(settings[key])
            except ValueError as error:
                raise ValueError("Invalid coordinate") from error
            if not minimum <= number <= maximum:
                raise ValueError("Invalid coordinate")
    if "TRIS_PORTFOLIO_FILE" in settings:
        portfolio_path = Path(settings["TRIS_PORTFOLIO_FILE"])
        if not portfolio_path.is_absolute() or portfolio_path.suffix.lower() != ".json":
            raise ValueError("TRIS_PORTFOLIO_FILE must be an absolute JSON path")
    if "TRIS_FITNESS_FILE" in settings:
        fitness_path = Path(settings["TRIS_FITNESS_FILE"])
        if not fitness_path.is_absolute() or fitness_path.suffix.lower() != ".json":
            raise ValueError("TRIS_FITNESS_FILE must be an absolute JSON path")
    return settings


def service_config(project: Path, home: Path, lan: bool = False, settings: dict | None = None) -> dict:
    python = project / ".venv" / "bin" / "python"
    log_dir = home / "Library" / "Logs" / "TrisDashboard"
    config = {
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
    if settings:
        config["EnvironmentVariables"] = dict(settings)
    return config


def run_launchctl(*arguments: str) -> None:
    subprocess.run(["launchctl", *arguments], check=True)


def require_macos() -> None:
    if sys.platform != "darwin":
        raise RuntimeError("Service management requires macOS")
    if os.geteuid() == 0:
        raise RuntimeError("Run as your regular macOS user, not sudo")


def install(project: Path, home: Path, lan: bool, settings_path: Path | None = None) -> None:
    require_macos()
    python = project / ".venv" / "bin" / "python"
    if not python.is_file():
        raise RuntimeError("Create .venv and install requirements first")
    path = agent_path(home)
    if path.exists():
        raise RuntimeError("Already installed. Run uninstall before reinstalling.")
    path.parent.mkdir(parents=True, exist_ok=True)
    (home / "Library" / "Logs" / "TrisDashboard").mkdir(parents=True, exist_ok=True)
    settings = read_public_settings(settings_path) if settings_path else {}
    path.write_bytes(plistlib.dumps(service_config(project, home, lan, settings)))
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
    parser.add_argument("--settings", type=Path, help="JSON file with public weather/GitHub configuration")
    args = parser.parse_args()
    project = Path(__file__).resolve().parent.parent
    home = Path.home()
    if (args.lan or args.settings) and args.command != "install":
        parser.error("--lan and --settings are only valid during install")
    try:
        if args.command == "install":
            install(project, home, args.lan, args.settings)
        elif args.command == "uninstall":
            uninstall(home)
        else:
            status()
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, "Error: " + str(error) + "\n")


if __name__ == "__main__":
    main()
