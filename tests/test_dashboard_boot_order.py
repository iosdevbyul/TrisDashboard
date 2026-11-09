from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_display_preferences_restore_before_dashboard_initial_poll():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert html.index('src="/static/preferences.js"') < html.index('src="/static/dashboard.js"')
    js = (ROOT / "frontend/static/dashboard.js").read_text(encoding="utf-8")
    assert 'if (!window.trisDashboardRefreshPaused) {' in js
    preferences = (ROOT / "frontend/static/preferences.js").read_text(encoding="utf-8")
    # Restore display and favorite order before the first dashboard API poll.
    assert 'buildControls(); restore(); restorePins(); buildPinButtons(); apply();' in preferences
    assert preferences.index('restore(); restorePins();') < preferences.index('buildPinButtons(); apply();')
