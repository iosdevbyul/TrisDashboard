from pathlib import Path


def test_periodic_refresh_does_not_interrupt_inflight_overview():
    source = (Path(__file__).resolve().parents[1] / "frontend/static/dashboard.js").read_text(encoding="utf-8")
    function = source.split("  function loadOverview(force) {", 1)[1].split("  document.getElementById(\"agenda-toggle\")", 1)[0]
    guard = "if (!force && overviewRequest && overviewRequest.readyState !== 4) { return; }"
    assert guard in function
    assert function.index(guard) < function.index("lastDataStarted = now;")
    assert "if (overviewRequest && overviewRequest.readyState !== 4) { overviewRequest.abort(); }" in function
