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


## Personal local agenda

Copy `examples/agenda.example.json` to a private MacBook file and set `TRIS_AGENDA_FILE` to the absolute path, including in the allowlisted launchd settings JSON if needed. The optional card shows a maximum of eight events occurring in the next 14 days. Each event requires a local `date` in YYYY-MM-DD and `title`, and optionally a 24-hour `time` in HH:MM. No Google/Apple calendar synchronization, notifications or recurring-event interpretation is implemented. The schedule is visible to clients on your trusted home LAN; never commit personal calendar data.


## GitHub per-repository health and PR previews

Each configured public repository has its own availability status. If one repo fails, other working repositories still show their PR counts and latest workflow status; total PR count is marked as **known** when incomplete. Up to three open PR titles are linked to GitHub per repository, and URLs are only rendered when they use the expected GitHub HTTPS prefix. Provider exception details are never passed to the browser. Rate-limit and private-repository constraints remain.


## Browser response safety and version refresh

The local server sets response headers to prevent MIME sniffing, iframe embedding and referrer leakage, plus a restrictive same-origin Content Security Policy. The dashboard HTML, API and health probe use `Cache-Control: no-store`; local static CSS and JS require revalidation so browser reloads can pick up deployed changes. Interactive API documentation and OpenAPI generation are disabled to reduce unnecessary LAN endpoints. These measures reduce accidental exposure but **do not provide authentication or HTTPS**. Any device allowed onto the trusted home LAN and able to reach the service can view the configured content; do not forward the port to the internet. CI additionally checks Python module compilation.


## Optional client IP admission control

Use `TRIS_ALLOWED_CLIENT_IPS` for an **optional** comma-separated list of exact source IPs and CIDR networks. Example: `127.0.0.1,192.168.1.0/24`. The MacBook launchd settings JSON also supports this non-secret option. The server compares the actual network peer address, **not** untrusted `X-Forwarded-For` headers. When unset, existing same-Wi-Fi connectivity remains unchanged; configure only after confirming your MacBook/iPad subnet, and include `127.0.0.1` if the local diagnostic tool needs access. A mismatched IP receives HTTP 403. This is source-address filtering, **not authentication**, and cannot protect data from other devices using an allowed IP/network or eavesdropping on unencrypted HTTP. Avoid public port forwarding.


## Data freshness and validation

A manual portfolio snapshot is labeled **OUTDATED** when its timezone-aware `as_of` timestamp is more than 72 hours old. Future timestamps more than ten minutes ahead are rejected, rather than misrepresented as current. The returned quality metadata includes age in hours and the threshold. A recent manual snapshot still means only that the file timestamp is recent: it **does not** mean real-time market prices. Missing position prices stay unavailable.


## Resilient browser refresh

The overview endpoint is normally refreshed every three minutes. Failed/invalid responses preserve the last displayed values and trigger bounded retry delays (30, 60, 120, up to 180 seconds). Recovery resets the failure counter. Retry timers are cleared when the browser is hidden or a new explicit refresh starts, and out-of-order replies are ignored. This behavior works with ES5-era JavaScript; final Safari 9 device checks remain outstanding.


## Offline deployment preflight

Before starting the MacBook LaunchAgent, validate the public, allowlisted settings and any configured personal data files **without sending them to an external service**:

```sh
.venv/bin/python -m macos.preflight --settings ~/tris-dashboard-settings.json
.venv/bin/python -m macos.preflight --settings ~/tris-dashboard-settings.json --json
```

The command returns non-zero when settings or a referenced local data file is invalid, and prints only `valid` / `invalid` / `not-configured` flags. It never prints private paths, portfolio values, calendar titles, or tokens. Unconfigured optional data panels are permitted. CI includes mocked end-to-end tests checking that JavaScript-rendered fields exist in the HTML and that local static assets resolve. This is not a substitute for booting the actual Mac or iPad; hardware verification remains the final step.

## Source overview accuracy

The at-a-glance status strip counts all seven external/local data sources (weather, GitHub, Trello, portfolio, workout, dividend, agenda). It flags outdated manual portfolio snapshots in the stale count, includes configured sources that are temporarily unavailable, and never counts the MacBook status as an external data source. Unconfigured optional sources remain excluded from unavailable counts.

## Trello count limits and credential rotation

The Trello overview requests at most 100 open cards per list. When that boundary is reached, the UI labels it **100+ / known cards**, rather than falsely claiming an exact count. Switching Trello key/token invalidates the cached board view, using a one-way digest as the in-process cache scope; raw credentials are never stored as cache keys or returned to clients. It remains a read-only optional integration; the Mac must provide its Trello credentials separately.


## Optional GitHub private repositories (server-side token)

To monitor non-public repositories, set `TRIS_GITHUB_TOKEN` **only in the MacBook backend process environment**, using a GitHub fine-grained personal access token with minimal read-only access to the specific repositories and their Actions data. If unset, the public no-token API behavior remains unchanged. Private repositories may require read permissions for **Pull requests** and **Actions**. Access varies by repository permissions and GitHub policy.

Never commit the token, put it in frontend JavaScript, a local portfolio file, or the allowlisted public launchd settings JSON. The authentication header is sent only by the MacBook server to GitHub's HTTPS API. Cached results are scoped by a one-way token digest to prevent stale data after rotation; no raw token is stored in cache. **Warning:** Private repository names and PR titles displayed in this dashboard are visible to any client that can access the MacBook's HTTP dashboard. Restrict access to trusted devices using the optional IP allowlist; this does not encrypt LAN traffic.

A secure macOS Keychain/launchd secret loader is not implemented yet, so the login-start LaunchAgent intentionally cannot persist the token through its public settings mechanism.


## Offline CSV import for workout summaries

If WakTrainer or another fitness source can provide a **CSV export** matching columns `date,type,duration_minutes,distance_km`, convert it locally into the existing private JSON format:

```sh
.venv/bin/python -m macos.import_workouts --input ~/Downloads/workouts.csv --output ~/tris-private/fitness.json --dry-run
.venv/bin/python -m macos.import_workouts --input ~/Downloads/workouts.csv --output ~/tris-private/fitness.json
```

The importer validates every record with the existing dashboard fitness parser, rejects malformed/nonfinite/negative measurements, caps file size and workouts, and performs an atomic replacement only after successful validation. Existing outputs require the explicit `--force` flag. Private output files are created with owner-only permissions on normal macOS systems. Set `TRIS_FITNESS_FILE` to the output path in the MacBook's configuration. **This is a manual CSV bridge, not an automatic WakTrainer/HealthKit synchronization.** No files are uploaded to an external server.

## Optional login-start provider credentials from macOS Keychain

The MacBook login agent can now use `--keychain`, which starts a small Python wrapper that reads optional GitHub/Trello credentials from the logged-in user's Keychain and then replaces itself with uvicorn. The wrapper **does not put secrets in the LaunchAgent plist, command arguments, or browser**. Create generic-password entries in macOS **Keychain Access** (login keychain), each with account `TrisDashboard` and the following service names: `ai.tris.dashboard.github` (GitHub token), `ai.tris.dashboard.trello-key` (Trello API key), `ai.tris.dashboard.trello-token` (Trello token). Your macOS version may show the service field as the item's name. Grant access to the Python interpreter used by `.venv` only when prompted; unattended startup can fail if the Keychain is locked or access requires approval.

Once the entries exist, stop any manually running server and use `.venv/bin/python -m macos.service install --lan --keychain --settings ~/tris-dashboard-settings.json` (omit `--settings` if unused). **Trello also requires `TRIS_TRELLO_BOARD_ID`**: this is a non-secret board identifier you can set in the public launchd settings JSON. Reinstall the user agent after changing settings. For security, never paste passwords or tokens into a terminal command's arguments or commit them to Git. No Keychain items are created by this code. On non-macOS hosts the wrapper is not supported.

## Offline portfolio and dividend CSV import

The MacBook can now convert CSV exports to private JSON without brokerage login or live market-price requests. Import columns for positions: `symbol,currency,quantity,price` (price may be blank). For confirmed distributions: `symbol,currency,paid_on,amount`. See `examples/portfolio.example.csv` and `examples/dividends.example.csv`.

```sh
.venv/bin/python -m macos.import_finance portfolio --input ~/Downloads/positions.csv --output ~/tris-private/portfolio.json --dry-run
.venv/bin/python -m macos.import_finance portfolio --input ~/Downloads/positions.csv --output ~/tris-private/portfolio.json
.venv/bin/python -m macos.import_finance dividends --input ~/Downloads/dividends.csv --output ~/tris-private/dividends.json
```

Conversions validate against the dashboard's original JSON parsers, write private files atomically, and require `--force` to replace an existing output. The portfolio's import time is recorded as `as_of` by default; this is **not the market quotation timestamp** and does not imply live prices. If you know the actual reference timestamp, pass the ISO 8601 `--as-of` value. Only record dividends actually received. Data remains local to the MacBook; external CSV schemas must be adapted before import.

## WakTrainer JSON export bridge (contract v1)

A versioned, opt-in JSON bridge is available as `.venv/bin/python -m macos.import_waktrainer --input ~/Downloads/waktrainer-export.json --output ~/tris-private/fitness.json --dry-run`. Remove `--dry-run` to write; use `--force` only to replace a previous output. It accepts a strictly validated, timezone-aware workout export and converts seconds/meters to minutes/kilometers. See `docs/WAKTRAINER_EXPORT_CONTRACT.md` and the example file. **The current WakTrainer app has not been verified to produce this export.** This is preparation for a future WakTrainer-side exporter, not a claim of automatic synchronization.

## Live MacBook deployment smoke test

After starting the server, run `.venv/bin/python -m macos.smoke` or `.venv/bin/python -m macos.smoke --json` on the MacBook. This tool checks only `http://127.0.0.1:8080`: health, dashboard HTML, all three local frontend assets, API payload shape, and security/cache headers. It counts ready, stale and unavailable sources without printing personal calendar events, positions, credentials or repository names. The tool exits with status 1 if the server or contract is broken; upstream optional integrations may be unavailable without failing the deployment check. When a custom IP allowlist is configured, allow loopback `127.0.0.1` for local smoke tests. It is an integration smoke test, not a long-duration physical Mac/iPad acceptance test.

## Checking login credentials without displaying secrets

Run `.venv/bin/python -m macos.doctor --keychain --json` on the MacBook to inspect only **presence booleans** of the optional GitHub token, Trello API key and Trello token. No token values, Keychain error strings or command-line secret arguments are printed. Missing Keychain entries remain optional: public GitHub monitoring, weather and local JSON cards still work. The service needs a logged-in macOS session, and macOS may prompt for Keychain access. An account configured with GitHub or Trello still needs the right repository/board permissions and board ID.

## Incremental WakTrainer import

Pass `--merge` instead of `--force` when importing another WakTrainer export into an existing private fitness JSON file. The importer first validates both the incoming export and existing history, then appends only previously unseen workout signatures and atomically writes the combined file. Repeating the same import does not create duplicate records; malformed input never overwrites history. **Limitation of v1:** without stable workout IDs, two distinct workouts with identical date, type, rounded duration and distance cannot be distinguished; they are treated as one. A future WakTrainer exporter with stable session IDs should upgrade the contract. A combined file remains subject to the 500-record limit. The Mac app still requires a user-provided export file; it is not automatic iOS syncing.

## Optional scheduled workout import on MacBook

If a separate process **already writes** the version 1 WakTrainer export JSON to a fixed private file, the MacBook can check for it every 15 minutes. Run `.venv/bin/python -m macos.periodic_workout install --input ~/tris-private/waktrainer-export.json --output ~/tris-private/fitness.json` as a logged-in macOS user to install an independent per-user LaunchAgent. The export file may not exist yet: the job quietly skips missing input, and repeat imports use the idempotent `--merge` behavior. To stop this scheduled import, run `.venv/bin/python -m macos.periodic_workout uninstall`. The job is **not automatically installed** during setup and does not create a source export, access the iOS app, communicate with iCloud, or wake a sleeping Mac. Do not put input/output files under the Git repository. Configure `TRIS_FITNESS_FILE` to the output path so the dashboard can show the records. Like v1 merge, two distinct sessions with identical measurements can collide; app-generated stable IDs are a future enhancement.

## Offline backup and restore of personal data

Back up the local JSON files configured in your Mac's allowlisted settings (portfolio, workout, dividends, agenda) to a **private destination outside this repository**:

```sh
.venv/bin/python -m macos.backup backup --settings ~/tris-dashboard-settings.json --directory ~/tris-private/backups/backup-001
.venv/bin/python -m macos.backup restore --settings ~/tris-dashboard-settings.json --directory ~/tris-private/backups/backup-001
.venv/bin/python -m macos.backup restore --settings ~/tris-dashboard-settings.json --directory ~/tris-private/backups/backup-001 --force
```

A new backup directory is created with owner-only file permissions and SHA-256 checksums. Existing backup directories are never silently overwritten; the manifest never contains personal file contents or original paths. Restore defaults to **validation only** and needs explicit `--force` before replacing any configured data file. The tool validates checksums and data schemas before writing. It backs up **only** explicitly configured local JSON files, not credentials or Keychain entries. Copies are plaintext, not encrypted: store on a protected Mac volume and do not place them in a public/synced directory. This is not a remote/cloud backup service. Stop background import jobs when restoring to avoid concurrent writes.

## Restore failure recovery

Restore validation now checks **both** backup file checksums and the dashboard data schemas, even without `--force`. During an explicit restore, prior versions of every destination are staged first. If a later file replacement fails, the command attempts to roll back files already replaced. A multi-file restore cannot be fully atomic across separate destinations or power loss; the rollback is best effort, and concurrent workout imports must be stopped before recovery. If rollback cannot complete, the command exits unsuccessfully; retain the original backup for manual recovery.

## Stable workout IDs (WakTrainer export v2)

The importer now supports interchange `schema_version: 2` with a **required stable `session_id`** for each workout. Two workouts with equal dates, duration and distance but different IDs no longer collapse into one record. Re-importing the same IDs remains idempotent. Version 1 files still work using the previous measurement-based fallback. See `examples/waktrainer-export-v2.example.json` and `docs/WAKTRAINER_EXPORT_CONTRACT.md`. The iOS app must still implement its own exporter and preserve the same IDs across exports.

## Dividend income history

The manually confirmed dividend card now displays the last six calendar months (including the current month) as currency-separated amounts. Months without recorded payments are shown explicitly, and historical figures remain **recorded receipts only**, not promised yields, price returns or estimated future dividends. This feature never converts USD and KRW or fetches investment prices.

## JavaScript browser smoke checks in CI

GitHub Actions now includes a separate Node.js job that parses both frontend scripts and executes the dashboard in a **network-free fake DOM with mocked API responses**. It verifies the initial time/data render, status summary, local settings controls and refresh action. This catches missing DOM elements and script exceptions earlier than Python-only tests. Node.js is a test runner **only**; the deployed MacBook server does not require Node. This test is not a real Safari 9 engine, so visual layout, older browser compatibility and long-duration hardware operation still require the final iPad mini acceptance test.

## Optional source-stamped market quotes (Twelve Data)

A **read-only**, opt-in market quote card supports at most **two** ticker symbols (for example `TRIS_QUOTE_SYMBOLS=JEPQ,QQQI`). Add this non-secret setting to the MacBook launch agent settings JSON. Set `TRIS_TWELVEDATA_API_KEY` only in the backend environment or as a generic-password item in the user's macOS login Keychain (service `ai.tris.dashboard.twelvedata`, account `TrisDashboard`) and enable the launchd `--keychain` option. Credentials are supplied to Twelve Data via its HTTPS `Authorization: apikey ...` header, never in URLs, JavaScript or log output. A 30-minute MacBook cache limits repeated requests; up to two HTTP API credits may be consumed per refresh depending on provider rules. Check your Twelve Data account's terms, access entitlements and rate limits before enabling it. This integration has no automatic subscription or billing flow.

The quote card renders **only the provider-reported price, currency and UTC source timestamp**, with an outdated marker after 72 hours. It does **not** replace manually entered portfolio valuations, claim true real-time pricing, convert currencies, guarantee the provider carries JEPQ/QQQI, or generate dividend forecasts. If the vendor rejects a symbol or API key, an unavailable state is shown. The quote endpoint is documented at <https://twelvedata.com/docs/markets/market-state>; actual provider responses cannot be validated by CI without a user-owned API key.

## Optional quote-derived partial portfolio value

When the owner has configured both a local portfolio snapshot and the optional Twelve Data source, the portfolio card adds a **separate** estimate for only those holdings where the vendor-returned ticker and currency match the local record. Each eligible record uses decimal arithmetic (quantity × provider-reported close). Outdated quotes are excluded, missing quotes remain **unvalued**, and USD/KRW totals are never combined. The UI displays how many holdings are covered and labels incomplete calculations **PARTIAL**. Original manual prices and position records are never overwritten. Quote values are not guaranteed real-time and should not be used as brokerage account statements or investment returns.

## Workout identity conflicts

The WakTrainer v2 importer now refuses to silently ignore a corrected or conflicting session that reuses an existing `session_id` with different metrics. It rejects the entire new import without changing the previous history and leaves conflict resolution to the owner/export producer. Existing exact-match records are still safely deduplicated. Legacy v1 exports containing duplicate measurement signatures are rejected to avoid double-counting.

## Browser recovery and quote display regression tests

The Node.js fake-browser CI now exercises overview API HTTP failure, bounded retry scheduling, successful recovery with provider-stamped quotes and partial portfolio valuation, and malformed JSON responses. Tests assert that previously rendered values are retained during failures, quote totals remain explicitly source-attributed, and data source status updates correctly. The checks require no real API token, broker account or external network; the final Safari 9 hardware test is still required.

### Quote timestamp freshness during caching

Each served quote re-evaluates the provider's original UTC timestamp against the current server time, even when the market response was loaded from the 30-minute cache. A stale quote cannot silently remain eligible for price-derived valuations simply because its cached `outdated` value was once false. Stored provider data is not modified by this check. The API remains optional and source-stamped; no paid market-data access is presumed.

### Market-data outage isolation

When **all** requested market symbols return unusable/error results, the failed response is not cached for a full 30 minutes. If a prior successful response exists, it may be shown as explicitly stale reference information; however **stale provider-cache results cannot be used for quote-based portfolio valuation**, regardless of the embedded quote timestamp. A partly failed batch still reports individual unavailable symbols and partial coverage. No new market data is fabricated during an outage.

## Local workout import concurrency

Both scheduled and manual WakTrainer JSON imports now acquire an exclusive advisory sidecar lock (`fitness.json.lock`) before reading or replacing history. This prevents two concurrent importer processes from independently reading the same old file and overwriting each other's newly imported workouts. The lock remains on disk (owner-only permissions) to avoid races with waiting processes. When `--merge` encounters no new sessions, it leaves the JSON untouched, including its modification time. Other programs writing the same JSON directly must also honor this lock; this is not distributed synchronization or iPhone-to-Mac transfer.

## Import preflight and lock file safety

WakTrainer `--dry-run` validates the source without creating a new output directory or lock file. A real import opens its persistent advisory lock using owner-only file permissions, verifies regular-file ownership and refuses unsafe or symlinked lock files. The scheduled importer always selects merge semantics under that lock, even when two scheduled invocations race to create the first JSON file. These protections are for a single trusted Mac user and are not a replacement for account permissions or encrypted storage.

## Workout import preview before transferring to dashboard

After exporting completed workout history from WakTrainer and saving the shared JSON file onto the MacBook (AirDrop/Files), preview it without modifying any records:

```sh
.venv/bin/python -m macos.preview_workouts --input ~/Downloads/waktrainer-export.json --output ~/tris-private/fitness.json
```

The preview validates both inputs, checks session-ID conflicts and reports only new/duplicate counts, combined total and earliest/latest dates. It never creates destination directories or writes output. If the summary is correct, use `.venv/bin/python -m macos.import_waktrainer --input ~/Downloads/waktrainer-export.json --output ~/tris-private/fitness.json --merge` to import. This remains user-controlled file transfer; there is no iPhone background upload.

## WakTrainer v2 workout history identity integrity

The MacBook fitness reader now rejects duplicate stable `session_id` values across **all** stored workouts, including records older than the visible seven-day window. Such a file is marked unavailable rather than silently double-counting activities. The internal API also reports the total history count and number of stable-ID records, allowing future migration checks. Legacy workouts without IDs remain readable. This does not change original workout records or automatically access HealthKit.

## Workout activity by day

The fitness card displays a seven-day, date-scoped activity breakdown with session counts, active minutes and kilometers per day, including explicit zeros on rest days. The same validated workout export drives the existing weekly aggregate and the daily rows; older workouts are excluded from both. No new HealthKit permissions, location traces or remote data access are introduced.

## Workout source file freshness

The local fitness panel now displays the MacBook workout JSON **file modification time in UTC**, and identifies a file not updated in more than seven days. This timestamp describes the last local file write, **not** the time of the most recent workout, a mobile sync, or data correctness. A week without exercising is not automatically an error, so the source does not become unavailable or mark data as stale solely because the file is old. No additional background network access is required.

## Receive user-shared WakTrainer workout files from Mac Downloads

WakTrainer's iOS export action creates a different `waktrainer-dashboard-UUID.json` filename each time. A new opt-in MacBook command recognizes those named exports in a specified local directory and merges all validated v2 sessions as a **single import**. Preview is the default and never writes:

```sh
.venv/bin/python -m macos.receive_workouts --directory ~/Downloads --output ~/tris-private/fitness.json
.venv/bin/python -m macos.receive_workouts --directory ~/Downloads --output ~/tris-private/fitness.json --apply
```

It reads only `waktrainer-dashboard-*.json` files owned by the logged-in Mac user, rejects symbolic links, caps the number of files and workout records, validates duplicates/conflicts before updating the private JSON, and refuses to erase existing history. Files are **not moved or deleted**, so re-running the command is idempotent; remove/archive older exports manually if the inbox exceeds 50 files. No device upload, cloud polling, root privileges or automatic watch service is added. The owner must first share files from iPhone to the chosen Mac folder (for example, AirDrop/Files).

## Optional automatic MacBook import of WakTrainer AirDrop files

After confirming that manually exported WakTrainer v2 files arrive in a dedicated Mac folder and `macos.receive_workouts` reports expected data, the owner can **explicitly install** a per-user macOS LaunchAgent that checks that folder every 15 minutes:

```sh
.venv/bin/python -m macos.periodic_inbox install --directory ~/Downloads --output ~/tris-private/fitness.json
.venv/bin/python -m macos.periodic_inbox run-once --directory ~/Downloads --output ~/tris-private/fitness.json
.venv/bin/python -m macos.periodic_inbox uninstall
```

The optional agent scans only the owner-created `waktrainer-dashboard-*.json` exports. It ignores unrelated downloads and keeps all original files; existing session IDs prevent duplicate imports. It will not start unless installed, will not request iOS access, and will not transfer files from the phone to the Mac. On errors (invalid files, conflicting IDs, more than 50 candidates), import fails rather than deleting originals. Use a dedicated folder and periodically archive old files to stay below this bound. The agent uses the already-tested locked atomic workout importer, and does not require credentials, extra cloud services or recurring subscriptions. Actual login-agent behavior remains for MacBook acceptance testing.

## Overlapping workout exports

WakTrainer exports complete history snapshots, so two or more shared JSON files often contain the same stable workout IDs. The inbox importer now counts and stages **unique sessions** before enforcing the 500-session history cap, instead of rejecting repeated full exports simply because their summed raw rows exceed 500. It still validates every source file and rejects conflicting records under the same stable ID. The summary distinguishes raw input rows, duplicates and genuinely new sessions.

## Check the automatic workout inbox without exposing personal data

Run `.venv/bin/python -m macos.periodic_inbox status` to see whether the optional per-user workout inbox LaunchAgent is installed, whether its configured folder is accessible, the number of matching shared JSON files, and whether the inbox has exceeded the 50-file limit. This is a **configuration and file-count inspection only**, not proof that launchd is currently executing or that all exports are valid. The summary intentionally omits workout names, file paths, profile details and access credentials. No scheduler is installed or modified by this status command.

## Choose workout calendar timezone at import

WakTrainer's iOS export records workout start times in UTC. If your local calendar day differs from UTC (for example an evening workout in Seoul), pass the **same optional IANA timezone** through preview and import:

```sh
.venv/bin/python -m macos.receive_workouts --directory ~/Downloads --output ~/tris-private/fitness.json --timezone Asia/Seoul
.venv/bin/python -m macos.receive_workouts --directory ~/Downloads --output ~/tris-private/fitness.json --timezone Asia/Seoul --apply
```

The `macos.import_waktrainer` and `macos.preview_workouts` commands also accept `--timezone`. With no flag, the original ISO timestamp's own date is preserved for backwards compatibility. Use a consistent timezone for future imports: changing it after previous imports may cause correctly detected stable-ID conflicts, requiring deliberate migration rather than silent history rewrites. No changes to workout UTC timestamps or device settings are made.

## Timezone-aware scheduled WakTrainer inbox

The optional MacBook inbox LaunchAgent can apply the same calendar timezone as manual import. Set it when you explicitly install the agent:

```sh
.venv/bin/python -m macos.periodic_inbox install --directory ~/Downloads --output ~/tris-private/fitness.json --timezone Asia/Seoul
.venv/bin/python -m macos.periodic_inbox status
```

The timezone name is a non-secret IANA identifier stored in the per-user launchd arguments. Existing installations without a timezone continue to work unchanged. To change an installed agent's timezone, first uninstall and then reinstall it with the desired flag; changing a timezone after data has been imported can yield stable-ID date conflicts that must be handled deliberately. The status command validates the configured timezone without disclosing private file paths or workouts. This does not run an iOS background synchronization service.
