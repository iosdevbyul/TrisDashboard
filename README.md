# TrisDashboard

Personal, dark-themed always-on display for **iPad mini 1 (iOS 9 Safari)** and iPhone. A MacBook hosts the server over trusted home Wi-Fi. No cloud services, subscriptions, Docker, or Apple developer certificate are required.

## First run on MacBook (Python 3.11+)

```sh
git clone https://github.com/iosdevbyul/TrisDashboard.git
cd TrisDashboard
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8080
```

Open http://127.0.0.1:8080 on the Mac. To test on an iPad or iPhone, stop the process and restart with `--host 0.0.0.0` on a **trusted private network only**. On the device, use `http://<macbook-lan-ip>:8080`. Both devices need the same network; macOS Firewall may request permission.

## Optional Mac login auto-start (launchd)

Set up `.venv` first. Run from the project directory, as your normal user (no sudo):

```sh
python3 -m macos.service install --lan
python3 -m macos.service status
```

`--lan` explicitly allows same-Wi-Fi devices; omit it for Mac-only localhost access. This creates a per-user LaunchAgent that starts on login and restarts when the server crashes. It does **not** install a system-wide daemon and it does not keep a sleeping Mac awake. To remove:

```sh
python3 -m macos.service uninstall
```

Logs: `~/Library/Logs/TrisDashboard/server.log` and `error.log`. If you move the repository or replace the virtual environment, uninstall and reinstall the service. Stop any manually started server before enabling launchd to avoid port conflicts.

**Power / reliability:** Keep the Mac awake while serving the dashboard. Confirm the device's auto-lock setting (where available); a Safari page cannot bypass iOS auto-lock. Monitor battery health/heat if using an old iPad continuously. A browser suspended while the device is locked cannot guarantee continuous updates.

**Security:** The service is intentionally unauthenticated; do not set router port forwarding or expose port 8080 publicly. Only enable LAN mode on a trusted Wi-Fi. Never embed API credentials or personal tokens in frontend assets. HTTP on the LAN is unencrypted.

## Tests

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

GitHub Actions checks Python 3.11, 3.12 and 3.13 for every PR and on main.

## Device acceptance checklist

1. On MacBook, load `/` and confirm the local clock, date and four placeholders.
2. On iPad mini 1, connect to the same Wi-Fi, open the Mac LAN URL in Safari, rotate to landscape. Confirm a two-column dark layout without horizontal scrolling.
3. On iPhone, check portrait layout has a single column, usable text and no clipping.
4. On iPad, use Safari **Add to Home Screen** to test an app-like launch (dependent on device/iOS behavior).
5. Restart/stop the Mac server. Check offline message appears and online recovery occurs within approximately 15–20 seconds once the server is reachable.
6. Leave the display running while the Mac stays awake and inspect for memory/refresh problems.

Actual iOS 9 device behavior is **not** simulated by backend CI; validate on the physical tablet.

## Available routes

- `/` dashboard
- `/healthz` JSON server health

Investments, GitHub/Trello, weather and workout panels intentionally show placeholders until server-side integrations arrive.
