"""Offline configuration and private-file preflight: never prints file paths or values."""
import argparse
import json
from pathlib import Path

from backend.agenda import load_agenda
from backend.dividends import load_dividends
from backend.fitness import load_fitness
from backend.portfolio import load_portfolio
from macos.service import read_public_settings

FILE_LOADERS = {
    "portfolio": ("TRIS_PORTFOLIO_FILE", load_portfolio),
    "fitness": ("TRIS_FITNESS_FILE", load_fitness),
    "dividends": ("TRIS_DIVIDENDS_FILE", load_dividends),
    "agenda": ("TRIS_AGENDA_FILE", load_agenda),
}


def inspect_settings(path: Path) -> dict:
    """Validate settings and configured private files without revealing their contents."""
    try:
        settings = read_public_settings(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"settings": "invalid", "files": {}, "ready": False}
    status = {}
    for label, (variable, loader) in FILE_LOADERS.items():
        if variable not in settings:
            status[label] = "not-configured"
            continue
        try:
            loader(Path(settings[variable]))
            status[label] = "valid"
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            status[label] = "invalid"
    return {"settings": "valid", "files": status,
            "ready": all(result != "invalid" for result in status.values())}


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline TrisDashboard configuration preflight")
    parser.add_argument("--settings", type=Path, required=True, help="Private launchd settings JSON path")
    parser.add_argument("--json", action="store_true", help="Print summary as JSON")
    args = parser.parse_args()
    result = inspect_settings(args.settings)
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print("Settings: " + result["settings"])
        for name, status in result["files"].items():
            print(name + ": " + status)
        print("Ready: " + ("yes" if result["ready"] else "no"))
    if not result["ready"]:
        parser.exit(1)


if __name__ == "__main__":
    main()
