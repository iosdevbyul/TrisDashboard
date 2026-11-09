from pathlib import Path


def test_periodic_health_poll_does_not_abort_unfinished_health_request():
    source = (Path(__file__).resolve().parents[1] / "frontend/static/dashboard.js").read_text(encoding="utf-8")
    function = source.split("  function checkServer() {", 1)[1].split("  function statusText(", 1)[0]
    guard = "if (request && request.readyState !== 4) { return true; }"
    assert guard in function
    assert function.index(guard) < function.index("lastRequestStarted = now;")
    assert "if (now - lastRequestStarted < 2000) { return false; }" in function
    assert "if (sequence === requestSequence) {" in function
    assert "setConnection(online);" in function
    assert "suppressNextReconnectRefresh = false;" in function
