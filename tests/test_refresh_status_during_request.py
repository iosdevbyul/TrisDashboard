from pathlib import Path


def test_elapsed_success_age_never_overwrites_pending_refresh_status():
    source = (Path(__file__).resolve().parents[1] / "frontend/static/dashboard.js").read_text(encoding="utf-8")
    function = source.split("  function updateLastSuccessAge() {", 1)[1].split("  function clearOverviewRetry()", 1)[0]
    assert "(overviewRequest && overviewRequest.readyState !== 4)" in function
    assert function.index("readyState !== 4") < function.index('text("data-refresh-state"')
