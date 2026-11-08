"""Manage a per-user launchd service for the MacBook dashboard.

This tool never changes power settings or opens firewall/router ports.
"""
import argparse
from backend.access import validate_allowlist
import json
import math
import os
import plistlib
from macos.agent_files import write_private_agent
import subprocess
import sys
from pathlib import Path

LABEL = "ai.tris.dashboard"
PORT = 8080


def agent_path(home: Path) -> Path:
    return home / "Library" / "LaunchAgents" / (LABEL + ".plist")


ALLOWED_SETTINGS = ("TRIS_LATITUDE", "TRIS_LONGITUDE", "TRIS_LOCATION_NAME", "TRIS_GITHUB_REPOS", "TRIS_PORTFOLIO_FILE", "TRIS_FITNESS_FILE", "TRIS_DIVIDENDS_FILE", "TRIS_AGENDA_FILE", "TRIS_ALLOWED_CLIENT_IPS", "TRIS_TRELLO_BOARD_ID", "TRIS_QUOTE_SYMBOLS")


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
            if not math.isfinite(number) or not minimum <= number <= maximum:
                raise ValueError("Invalid coordinate")
    project = Path(__file__).resolve().parent.parent
    for key in ("TRIS_PORTFOLIO_FILE", "TRIS_FITNESS_FILE",
                "TRIS_DIVIDENDS_FILE", "TRIS_AGENDA_FILE"):
        if key in settings:
            private_path = Path(settings[key])
            if not private_path.is_absolute() or private_path.suffix.lower() != ".json":
                raise ValueError(key + " must be an absolute JSON path")
            resolved = private_path.resolve()
            if resolved == project or project in resolved.parents:
                raise ValueError(key + " must be outside the repository")
    if "TRIS_QUOTE_SYMBOLS" in settings:
        from backend.quotes import quote_symbols
        settings["TRIS_QUOTE_SYMBOLS"] = ",".join(quote_symbols(settings["TRIS_QUOTE_SYMBOLS"]))
    if "TRIS_ALLOWED_CLIENT_IPS" in settings:
        settings["TRIS_ALLOWED_CLIENT_IPS"] = validate_allowlist(settings["TRIS_ALLOWED_CLIENT_IPS"])
    return settings


def service_config(project: Path, home: Path, lan: bool = False, settings: dict | None = None,
                   keychain: bool = False) -> dict:
    python = project / ".venv" / "bin" / "python"
    log_dir = home / "Library" / "Logs" / "TrisDashboard"
    config = {
        "Label": LABEL,
        "ProgramArguments": [
            str(python), "-m", "macos.secure_launch" if keychain else "uvicorn",
            *([] if keychain else ["backend.app:app"]),
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


def install(project: Path, home: Path, lan: bool, settings_path: Path | None = None,
            keychain: bool = False) -> None:
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
    write_private_agent(path, service_config(project, home, lan, settings, keychain=keychain))
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
    parser.add_argument("--settings", type=Path, help="JSON file with non-secret configuration")
    parser.add_argument("--keychain", action="store_true",
                        help="Load GitHub/Trello credentials from the user's macOS Keychain")
    args = parser.parse_args()
    project = Path(__file__).resolve().parent.parent
    home = Path.home()
    if (args.lan or args.settings or args.keychain) and args.command != "install":
        parser.error("--lan and --settings are only valid during install")
    try:
        if args.command == "install":
            install(project, home, args.lan, args.settings, keychain=args.keychain)
        elif args.command == "uninstall":
            uninstall(home)
        else:
            status()
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, "Error: " + str(error) + "\n")


if __name__ == "__main__":
    main()
