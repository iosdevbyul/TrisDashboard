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

Then install with `python3 -m macos.service install --lan --settings ~/tris-dashboard-settings.json`. Settings are validated and embedded in the per-user LaunchAgent plist, so change them by uninstalling and reinstalling the agent. Only allowlisted **non-secret** configuration values are permitted, including optional local portfolio and fitness JSON file paths. Never put tokens/passwords in this file. Service starts on login, not while MacBook sleeps. Logs: `~/Library/Logs/TrisDashboard/`.

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


## Optional Trello board (read-only)

Trello integration is optional. Supply `TRIS_TRELLO_BOARD_ID`, `TRIS_TRELLO_KEY`, and `TRIS_TRELLO_TOKEN` as **MacBook server environment variables** to show counts and a few card names from lists named Next, In Progress, and Done. It does not create, update, or move Trello cards. Provider results are cached for 10 minutes.

Do not put these credentials in frontend files, GitHub commits, or the public launchd settings JSON. For a login-start service, provide secrets through a separately managed secure launcher/keychain workflow in a future release; the current public settings installer intentionally rejects tokens. If no credentials are supplied, the Trello panel shows Not configured.


## Desk display diagnostics and weather details

The MacBook server's `/api/overview` includes local process uptime and UTC server time. This is the **dashboard process uptime**, not physical Mac uptime, and does not reveal hostnames or local filesystem information. The UI shows the last successful response even while the server is unreachable.

Weather additionally shows apparent temperature, today's high/low and maximum precipitation probability when provided by Open-Meteo. If optional forecast fields are missing, basic current temperature and humidity still render.

Keep the tablet's Safari page visible while using the desk display. Device-specific checks are intentionally deferred to the final acceptance phase.


## Manual investment dashboard (no brokerage connection)

The portfolio panel reads an optional JSON snapshot **from the MacBook only**. Copy `examples/portfolio.example.json` outside this repository (e.g. `~/tris-private/portfolio.json`), replace demo holdings and timestamp with your own data, and set `TRIS_PORTFOLIO_FILE` to its absolute path before launching the server.

- Quantity and optional price are manually entered. No market quote provider, automated price refresh, realized gains, dividends, brokerage API, or account authentication is provided yet.
- `as_of` is a timezone-aware ISO-8601 snapshot timestamp. Values are explicitly marked as **manual snapshots**, never live prices.
- Valuations are calculated within each currency independently, with no implied FX conversion.
- Missing prices display "price unavailable" rather than inventing valuation.
- Keep your personal holdings file outside the public GitHub repository and outside the `frontend/` directory. Anyone on the trusted LAN who can reach the dashboard can view the displayed holdings.
- If the file cannot be read, the card shows an unavailable state. Restart the launchd service to apply a new `TRIS_PORTFOLIO_FILE` environment variable once configured via a secure deployment workflow.


## Local display preferences

Each device has its own settings stored in browser localStorage. Select **Display settings** to toggle compact cards, reduce display brightness with a darker CSS theme, or hide individual panels; **Reset display** restores all panels. **Refresh now** reloads the current page. These preferences stay on the device and do not sync between iPad/iPhone. If Safari storage is disabled or wiped, the default display is used; no server credentials are stored there.

For login-start portfolio loading, set a private **absolute JSON file path** under `TRIS_PORTFOLIO_FILE` in the Mac public settings JSON. This stores only the path in the per-user LaunchAgent plist, not portfolio contents or tokens. Keep your snapshot outside the repository. Reinstall the user agent after changing its settings.


## Local fitness summary

Fitness reads an optional MacBook-only JSON workout export, without requesting HealthKit permissions or pretending to synchronize WakTrainer. Copy `examples/fitness.example.json` to a private folder, replace with real workouts, and set `TRIS_FITNESS_FILE` to an absolute JSON file path. A rolling 7-day inclusive period shows sessions, minutes, kilometers, and up to five recent workouts. Missing or invalid exports show a clearly marked unavailable panel. Keep personal workout data out of Git and out of `frontend/`. To use login auto-start, add the absolute `TRIS_FITNESS_FILE` path to the nonsecret launchd settings JSON and reinstall the agent.


## At-a-glance desk mode

The top strip reports the number of ready configured or public data sources, stale/unavailable counts and time of the last successfully parsed overview response. The source count covers weather, GitHub, Trello, portfolio and fitness (five possible panels); sources without configuration are not counted as available. Glance mode compresses card layout and clips lengthy details for desk viewing. The preference is stored separately on each browser and remains optional. It is **not** a substitute for real-device visual acceptance.


## Provider timeout isolation

Weather, GitHub and Trello are collected concurrently by the MacBook server. The overview waits at most four seconds for remote results, so one stuck provider does not prevent local fitness/portfolio and other completed providers from rendering. Slow or failed services appear unavailable/stale without returning exception text or credentials. Unfinished provider requests are reused until finished instead of adding an unlimited queue. Browser overview timeout is 10 seconds and stale/out-of-order responses are ignored. Polling remains conservative and provider result caching still applies.


## One-command MacBook setup and diagnostics

On the MacBook, after cloning the repository, run `sh scripts/setup-mac.sh` to check for Python 3.11+, create `.venv`, and install server dependencies. This script does **not** start or expose a server or install launchd. Check local setup later using `.venv/bin/python -m macos.doctor` or `.venv/bin/python -m macos.doctor --json` for script-friendly status.

The doctor reports Python compatibility, local environment existence, whether the per-user LaunchAgent exists, and whether `127.0.0.1:8080/healthz` responds. It does not print keys, tokens or personal data. Start on localhost with `.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8080`. To allow an iPad on **trusted home Wi-Fi**, explicitly opt in with `.venv/bin/python -m macos.service install --lan` after stopping any manually started service. Make sure the Mac stays awake and never configure public router forwarding.


## Confirmed dividend payment ledger

Copy `examples/dividends.example.json` to a private MacBook file and replace the demo with **actual confirmed receipts**. Set `TRIS_DIVIDENDS_FILE` to its absolute JSON path, or add that path to the allowlisted non-secret launchd settings JSON and reinstall the agent. Each entry has `symbol`, `paid_on` (YYYY-MM-DD), `currency` (USD or KRW), and `amount` (a nonnegative amount recorded for that payment). The panel shows calendar-month totals per currency and recent recorded payments, without FX conversion or speculative future distributions. Never put sensitive holdings or account information in Git. No live broker, issuer, or dividend forecast service is connected.
