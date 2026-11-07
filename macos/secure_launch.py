"""Read optional provider credentials from the logged-in user's macOS Keychain."""
import argparse
import os
import subprocess
import sys

SERVICE_NAMES = {
    "TRIS_GITHUB_TOKEN": "ai.tris.dashboard.github",
    "TRIS_TRELLO_KEY": "ai.tris.dashboard.trello-key",
    "TRIS_TRELLO_TOKEN": "ai.tris.dashboard.trello-token",
    "TRIS_TWELVEDATA_API_KEY": "ai.tris.dashboard.twelvedata",
}
KEYCHAIN_ACCOUNT = "TrisDashboard"


def keychain_value(service: str, *, runner=subprocess.run) -> str | None:
    """Return only a Keychain value; never print it or put it in launchd plist."""
    result = runner(
        ["security", "find-generic-password", "-s", service, "-a", KEYCHAIN_ACCOUNT, "-w"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        return None
    return result.stdout.rstrip("\r\n") or None


def credential_status(*, lookup=keychain_value) -> dict:
    """Only availability booleans; never expose token bytes or keychain error text."""
    available = {}
    for name, service in SERVICE_NAMES.items():
        try:
            available[name] = bool(lookup(service))
        except OSError:
            available[name] = False
    return available


def provider_environment(base: dict | None = None, *, lookup=keychain_value) -> dict:
    env = dict(os.environ if base is None else base)
    for name, service in SERVICE_NAMES.items():
        try:
            value = lookup(service)
        except OSError:
            value = None
        if value is not None:
            env[name] = value
    return env


def main() -> None:
    parser = argparse.ArgumentParser(description="Start TrisDashboard with macOS Keychain provider credentials")
    parser.add_argument("--host", choices=("127.0.0.1", "0.0.0.0"), default="127.0.0.1")
    parser.add_argument("--port", type=int, choices=(8080,), default=8080)
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.exit(1, "macOS Keychain launch is only supported on macOS.\n")
    env = provider_environment()
    argv = [sys.executable, "-m", "uvicorn", "backend.app:app",
            "--host", args.host, "--port", str(args.port)]
    os.execve(sys.executable, argv, env)


if __name__ == "__main__":
    main()
