# TrisDashboard

Personal, dark-themed always-on display for **iPad mini 1 (iOS 9 Safari)** and iPhone. A MacBook hosts the server over trusted home Wi-Fi. No cloud subscription, Docker, or Apple developer certificate is required.

## First run on MacBook (Python 3.11+)

```sh
git clone https://github.com/iosdevbyul/TrisDashboard.git
cd TrisDashboard
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8080
```

Open http://127.0.0.1:8080 on the Mac. For iPad/iPhone on trusted Wi-Fi, run with `--host 0.0.0.0` and open `http://<macbook-lan-ip>:8080`.

## Live data configuration

Dashboard refreshes every 3 minutes in the browser. MacBook caches remote data (weather for 10 minutes, GitHub for 15 minutes), uses 5-second upstream timeouts and shows previous data marked stale on a provider outage.

Weather uses the free Open-Meteo current forecast endpoint. Defaults to central Seoul; you may configure location using environment variables before launching the server:

```sh
export TRIS_LATITUDE=37.5665
export TRIS_LONGITUDE=126.9780
export TRIS_LOCATION_NAME=Seoul
export TRIS_GITHUB_REPOS=iosdevbyul/TrisDashboard,iosdevbyul/DonghakStockVision
```

GitHub uses the public read-only REST API for open PR counts (up to 20 per repository) and latest Actions workflow run status, with no credentials required. Set `TRIS_GITHUB_REPOS` to a comma-separated list of up to 6 **public** repositories. Private repo support is deferred. Default is only TrisDashboard. Public API limits (60 requests/hour per IP) may apply; the 15-minute cache keeps at most six repositories near or under this budget for this app alone. Data integrations are server-only; do not put tokens in browser scripts. Weather data requires outbound internet access from the Mac.

## Optional login auto-start (launchd)

Create the virtual environment first. Run as your normal macOS user, no sudo:

```sh
python3 -m macos.service install --lan
python3 -m macos.service status
```

`--lan` enables the trusted Wi-Fi client connection. Without it, the service binds only localhost. To uninstall: `python3 -m macos.service uninstall`.

To configure weather and GitHub repositories for automatic launches, create a JSON file **outside the public web directory**, e.g. `~/tris-dashboard-settings.json`:

```json
{
  "TRIS_LATITUDE": 37.5665,
  "TRIS_LONGITUDE": 126.9780,
  "TRIS_LOCATION_NAME": "Seoul",
  "TRIS_GITHUB_REPOS": "iosdevbyul/TrisDashboard,iosdevbyul/DonghakStockVision"
}
```

Then install with `python3 -m macos.service install --lan --settings ~/tris-dashboard-settings.json`. Settings are validated and embedded in the per-user LaunchAgent plist, so change them by uninstalling and reinstalling the agent. Only the four **non-secret** public settings above are permitted. Never put tokens/passwords in this file. Service starts on login, not while MacBook sleeps. Logs: `~/Library/Logs/TrisDashboard/`.

## Security & compatibility

The service has no login and uses unencrypted HTTP on the home LAN. Do not expose port 8080 to the public internet. Keep the Mac awake for uninterrupted service. iOS 9 Safari uses ES5 JS / conservative CSS; validate against the real iPad. Long-running background browser refresh is not guaranteed when locked or suspended.

## Tests

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

CI checks Python 3.11, 3.12, and 3.13. Tests mock external providers and require no external network.

## Device acceptance

1. Mac and iPad/iPhone share trusted Wi-Fi, load the dashboard URL, and verify landscape/portrait layouts.
2. Verify current weather and GitHub open PRs update; temporarily cut Mac internet to test stale weather display.
3. Stop the Mac server and confirm offline banner; restart and check connection recovery.
4. Add to iPad Home Screen if desired. Validate auto-lock, charging heat and long-running rendering on the physical iPad.
