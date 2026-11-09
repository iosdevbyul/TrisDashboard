from pathlib import Path


def test_initial_paused_dashboard_displays_actionable_status_without_fetch():
    source = (Path(__file__).resolve().parents[1] / "frontend/static/dashboard.js").read_text(encoding="utf-8")
    init = source.split("  tick();\n  checkServer();", 1)[1].split("  setInterval(tick, 1000);", 1)[0]
    assert 'if (!window.trisDashboardRefreshPaused) {' in init
    assert 'loadOverview(true);' in init
    assert 'Press Refresh now to load data.' in init
    assert init.index("loadOverview(true);") < init.index("} else {")
