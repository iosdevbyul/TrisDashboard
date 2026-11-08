"""Run the real dashboard server twice on ephemeral localhost sockets.

No external provider requests are made: only /healthz is checked.
"""
import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def one_cycle(project: Path, *, timeout_seconds: float = 10.0) -> bool:
    """Start, probe, and stop uvicorn using a parent-owned local listening socket."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(5)
        port = listener.getsockname()[1]
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.app:app",
             "--fd", str(listener.fileno()), "--no-access-log"],
            cwd=str(project), pass_fds=(listener.fileno(),),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    return False
                try:
                    with urlopen("http://127.0.0.1:" + str(port) + "/healthz",
                                 timeout=0.5) as reply:
                        if reply.status == 200 and json.load(reply) == {"status": "ok"}:
                            return True
                except (OSError, ValueError, URLError):
                    time.sleep(0.1)
            return False
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def check_restart(project: Path) -> dict:
    first = one_cycle(project)
    second = one_cycle(project) if first else False
    return {
        "passed": bool(first and second),
        "first_start_passed": first,
        "restart_passed": second,
        "local_only": True,
        "provider_requests": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic localhost dashboard restart check")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    project = Path(__file__).resolve().parent.parent
    try:
        outcome = check_restart(project)
    except (OSError, ValueError, subprocess.SubprocessError):
        outcome = {"passed": False, "first_start_passed": False,
                   "restart_passed": False, "local_only": True,
                   "provider_requests": 0}
    if args.json:
        print(json.dumps(outcome, sort_keys=True))
    else:
        print("Local server start + restart: " + ("passed" if outcome["passed"] else "failed"))
    if not outcome["passed"]:
        parser.exit(1)


if __name__ == "__main__":
    main()
