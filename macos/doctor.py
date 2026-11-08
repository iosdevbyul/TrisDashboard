"""Local operational preflight with deliberately non-sensitive output."""
import argparse
import json
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from macos.service import agent_path
from macos.secure_launch import credential_status


def probe_server(url: str = "http://127.0.0.1:8080/healthz") -> bool:
    try:
        with urlopen(url, timeout=2) as response:
            if response.status != 200:
                return False
            data = response.read(513)
            if len(data) > 512:
                return False
            return json.loads(data) == {"status": "ok"}
    except (OSError, ValueError, URLError):
        return False


def inspect(project: Path, home: Path, *, probe=probe_server, python_version=None) -> dict:
    version = python_version or sys.version_info[:3]
    venv = project / ".venv" / "bin" / "python"
    agent = agent_path(home)
    return {
        "python_supported": tuple(version[:2]) >= (3, 11),
        "venv_created": venv.is_file(),
        "launch_agent_installed": agent.is_file(),
        "local_server_reachable": bool(probe()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the local MacBook dashboard deployment")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable status")
    parser.add_argument("--keychain", action="store_true",
                        help="Check presence of optional provider credentials without printing them")
    args = parser.parse_args()
    project = Path(__file__).resolve().parent.parent
    result = inspect(project, Path.home())
    if args.keychain:
        result["credentials_present"] = credential_status()
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        for key, value in result.items():
            print(key.replace("_", " ") + ": " + ("OK" if value else "NOT READY"))
        print("Only checks localhost; no API credentials or personal data are displayed.")


if __name__ == "__main__":
    main()
