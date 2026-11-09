from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_display_preferences_restore_before_dashboard_initial_poll():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert html.index('src="/static/preferences.js"') < html.index('src="/static/dashboard.js"')
    js = (ROOT / "frontend/static/dashboard.js").read_text(encoding="utf-8")
    assert 'if (!window.trisDashboardRefreshPaused) {' in js
    preferences = (ROOT / "frontend/static/preferences.js").read_text(encoding="utf-8")
    assert 'buildControls(); restore(); apply();' in preferences
