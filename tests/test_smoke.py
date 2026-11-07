from fastapi.testclient import TestClient

from backend import app as app_module
from macos.smoke import ASSETS, check_deployment

client = TestClient(app_module.app)


def fetch(path):
    response = client.get(path)
    return response.status_code, dict(response.headers), response.content


def test_live_smoke_reports_safe_counts_without_personal_data(monkeypatch):
    monkeypatch.setattr(app_module, "overview", lambda: {
        "weather": {"available": True, "temperature_c": 23.2},
        "github": {"available": False, "configured": True, "error": "private-repo-name"},
        "trello": {"available": False, "configured": False},
        "portfolio": {"available": True, "quality": {"outdated": True},
                      "positions": [{"symbol": "PRIVATE"}]},
        "fitness": {"available": False, "configured": False},
        "dividends": {"available": False, "configured": False},
        "agenda": {"available": False, "configured": False},
    })
    result = check_deployment(fetch)
    assert result["passed"]
    assert result["sources_ready"] == 2
    assert result["sources_stale"] == 1
    assert result["sources_unavailable"] == 1
    assert "PRIVATE" not in str(result)
    assert "private-repo-name" not in str(result)


def test_smoke_catches_missing_asset(monkeypatch):
    monkeypatch.setattr(app_module, "overview", lambda: {
        **{key: {"available": False, "configured": False} for key in (
            "weather", "github", "trello", "portfolio", "fitness", "dividends", "agenda")}
    })
    def broken(path):
        if path == "/static/dashboard.js":
            return 404, {}, b""
        return fetch(path)
    result = check_deployment(broken)
    assert result["health"]
    assert not result["assets"]
    assert not result["passed"]


def test_smoke_unreachable_local_server():
    def offline(path):
        raise OSError("connection refused: sensitive host")
    result = check_deployment(offline)
    assert result["passed"] is False
    assert "sensitive host" not in str(result)


def test_smoke_checks_all_three_local_assets():
    assert len(ASSETS) == 3
    assert "/static/preferences.js" in ASSETS
