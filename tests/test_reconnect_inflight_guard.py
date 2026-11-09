from pathlib import Path


def test_reconnect_keeps_pending_overview_request_alive():
    source = (Path(__file__).resolve().parents[1] / "frontend/static/dashboard.js").read_text(encoding="utf-8")
    assert 'if (wasOffline) {' in source
    assert '(!overviewRequest || overviewRequest.readyState === 4)) { loadOverview(true); }' in source
    assert 'if (overviewRequest && overviewRequest.readyState !== 4) { overviewRequest.abort(); }' in source
