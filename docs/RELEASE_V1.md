# TrisDashboard v1.0 release acceptance

Status: **Feature freeze / release candidate preparation** (2026-11-10).
This document defines the exit criteria for v1.0. It does **not** assert that physical acceptance or a GitHub Release has occurred.

## Scope and freeze

- Product: MacBook-hosted, trusted-LAN dashboard, designed for iPad mini 1 / iOS 9 Safari and modern browsers.
- Baseline reviewed at freeze: main commit `7b6782fcf52c3f83f403bcff1d4fb0a4b39a5588` (merged PR #340).
- No new features for v1.0. Only release-blocking bug fixes, tests, deployment or security fixes, and documentation changes.
- No new paid API subscriptions, public port forwarding, or credentials embedded in the browser.
- Feature work for later versions must be deferred, not silently added to v1.0.

## Release gates

- [x] Main has no open PRs at freeze checkpoint (2026-11-10).
- [x] Latest main GitHub Actions completed successfully at freeze checkpoint: https://github.com/iosdevbyul/TrisDashboard/actions/runs/42769035708
- [ ] MacBook host acceptance performed and evidence recorded.
- [ ] Physical iPad mini 1 / iOS 9 Safari acceptance performed and evidence recorded.
- [ ] Security, offline recovery, persistence and long-running display checks passed on actual hardware.
- [ ] Remaining failures triaged: blockers fixed/tested, non-blockers documented.
- [ ] Re-run required main CI after any release-blocking fix.
- [ ] Tag `v1.0.0` at the **final accepted main SHA**, then publish release notes. Do not tag the unverified candidate as stable.

## MacBook acceptance (real environment)

Record macOS version, Python version, `git rev-parse HEAD`, test date and observations.

1. With the repository checked out at the release candidate, run `sh scripts/setup-mac.sh`; confirm successful setup.
2. Run `.venv/bin/python -m macos.doctor` and `.venv/bin/python -m pytest -q`. Record any failures without publishing secret values.
3. Verify local `http://127.0.0.1:8080/healthz` and dashboard loading after starting the documented local server, or inspect an existing launchd installation using `.venv/bin/python -m macos.service status`.
4. Verify user-level launchd startup/restart on login and recovery after a stopped/restarted service. Capture sanitized diagnostic output.
5. For iPad testing, enable LAN access **only on trusted Wi-Fi** using the documented `macos.service install --lan` path. Confirm no public router forwarding, Internet-facing exposure, or secrets in frontend/static or screenshots.
6. Check configured/unconfigured provider behavior, local data paths, failure isolation, and a server outage/recovery. Do not consume paid quote APIs merely for acceptance.
7. Validate backup preview, selective restore, undo and dry-run operations without modifying production data unintentionally.

## iPad mini 1 acceptance (real iOS 9 Safari)

Record hardware, iOS/Safari version, candidate SHA, orientation, screenshots and any errors.

1. Open `http://<macbook-lan-ip>:8080` on the same trusted Wi-Fi network.
2. Verify portrait and landscape layout, text readability, scrolling, panels, quick links, search and focus navigation. Test touch controls separately from keyboard-only shortcuts.
3. Verify legacy JavaScript operation: clock, regular refresh, panel views and favorites, settings persistence across reload, and backup JSON preview/restore/undo.
4. Verify the visible stale-data/offline banner when Mac/server or network is unreachable and recovery after restoration.
5. Run a supervised long display session and record refresh behavior, battery/charging temperature, browser suspension and any reloads. Do not claim guaranteed background refresh.
6. Confirm that all optionally unconfigured integrations fail gracefully. Keep credentials and private local data outside screenshots/logs.

## Evidence and decision record

Record results on the existing TrisDashboard Trello **Final MacBook and iPad mini 1 acceptance** card, linked to this document. For each failed test, capture reproducible steps, expected/actual behavior and affected device. Use a normal feature branch and CI-gated PR only for blocking fixes.

Release decision:
- **GO**: all gates passed, no unresolved blocking issues, evidence attached, accepted main SHA recorded.
- **NO-GO**: any unverified physical gate, critical malfunction, unsafe LAN exposure, or data-loss issue.
- This release candidate remains **NO-GO pending real-device acceptance** until explicitly verified.

## Draft v1.0.0 release notes (publish only after GO)

TrisDashboard v1.0.0: personal MacBook-hosted dashboard for an older iPad mini 1 on trusted Wi-Fi, with status, weather, public GitHub activity, optional Trello/portfolio/dividend/agenda/fitness integrations, customizable panels and shortcuts, offline/stale indicators, local layout backup/restore and diagnostics. External integrations depend on configuration and connectivity; no guarantee of live brokerage feeds. Keep the Mac awake and the dashboard on a trusted local network.
