"""Create an owner-only, opt-in local settings template without secrets."""
import argparse
import json
import os
from pathlib import Path

from macos.service import ALLOWED_SETTINGS

DEFAULTS = {
    "TRIS_LOCATION_NAME": "Seoul",
    "TRIS_GITHUB_REPOS": "iosdevbyul/TrisDashboard",
}


def create_settings(destination: Path, *, fitness: Path | None = None) -> dict:
    destination = destination.expanduser().resolve()
    project = Path(__file__).resolve().parent.parent
    if destination == project or project in destination.parents or destination.suffix.lower() != ".json":
        raise ValueError("Configuration must be a private JSON file outside the repository")
    if destination.exists():
        raise ValueError("Configuration already exists; no overwrite permitted")
    if not destination.parent.is_dir():
        raise ValueError("Create the private settings directory first")
    settings = dict(DEFAULTS)
    if fitness is not None:
        file = fitness.expanduser().resolve()
        if file == project or project in file.parents or file.suffix.lower() != ".json":
            raise ValueError("Fitness file must be private JSON outside repository")
        settings["TRIS_FITNESS_FILE"] = str(file)
    # Validate BEFORE creating; do not write any API keys or tokens.
    # Verify all keys against the launch agent allowlist before writing.
    if not set(settings).issubset(ALLOWED_SETTINGS):
        raise ValueError("Unsupported setting")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(destination, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(settings, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return {"created": True, "settings_keys": sorted(settings)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a private non-secret dashboard configuration")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fitness", type=Path)
    args = parser.parse_args()
    try:
        result = create_settings(args.output, fitness=args.fitness)
    except (OSError, ValueError):
        parser.exit(1, "Configuration creation failed; check private location and existing files.\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
