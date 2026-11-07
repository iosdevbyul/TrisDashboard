#!/bin/sh
# Run from anywhere; installs only local Python dependencies, not a network service.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || {
  echo "Python 3.11 or newer is required." >&2
  exit 1
}
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m macos.doctor
printf '\nSetup completed. To run locally: .venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8080\n'
printf 'For trusted home Wi-Fi launch on login: .venv/bin/python -m macos.service install --lan\n'
