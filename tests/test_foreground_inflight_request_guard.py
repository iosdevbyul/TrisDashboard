from pathlib import Path


def test_foreground_transition_does_not_abort_active_overview():
    source = (Path(__file__).resolve().parents[1] / "frontend/static/dashboard.js").read_text(encoding="utf-8")
    handler = source.split('  document.addEventListener("visibilitychange", function () {', 1)[1]
    assert "(!overviewRequest || overviewRequest.readyState === 4)" in handler
    assert handler.index("(!overviewRequest || overviewRequest.readyState === 4)") < handler.index("loadOverview(true);")
    assert "if (!window.trisDashboardRefreshPaused" in handler
