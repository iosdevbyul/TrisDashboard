from pathlib import Path


def test_periodic_refresh_does_not_bypass_retry_backoff():
    source = (Path(__file__).resolve().parents[1] / "frontend/static/dashboard.js").read_text(encoding="utf-8")
    loop = source.split("    var interval = window.trisDashboardRefreshMinutes || 3;", 1)[1].split("  }, 60000);", 1)[0]
    assert "overviewRetryTimer === null" in loop
    assert loop.index("overviewRetryTimer === null") < loop.index("loadOverview(false)")
    assert "if (!document.hidden && !window.trisDashboardRefreshPaused)" in source
