from fastapi.testclient import TestClient
from backend.app import app
from backend import app as app_module

client = TestClient(app)


def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dashboard_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "TRIS DASHBOARD" in response.text
    assert "apple-mobile-web-app-capable" in response.text
    assert 'id="offline-banner"' in response.text
    assert 'id="weather-temp"' in response.text


def test_static_assets():
    for path in ("/static/style.css", "/static/dashboard.js"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.content


def test_legacy_js_avoids_unsupported_syntax():
    script = client.get("/static/dashboard.js").text
    for unsupported in ("const ", "let ", "=>", "fetch(", "?.", "??"):
        assert unsupported not in script
    assert "XMLHttpRequest" in script


def test_overview_endpoint(monkeypatch):
    monkeypatch.setattr(app_module, "overview", lambda: {"weather": {"available": False}, "github": {"available": False}})
    response = client.get("/api/overview")
    assert response.status_code == 200
    assert response.json()["weather"]["available"] is False
    assert response.headers["cache-control"] == "no-store"


def test_overview_includes_server_uptime(monkeypatch):
    monkeypatch.setattr(app_module, "overview", lambda: {"weather": {}, "github": {}, "trello": {}})
    response = client.get("/api/overview")
    assert response.status_code == 200
    server = response.json()["server"]
    assert server["available"] is True
    assert server["uptime_seconds"] >= 0
    assert server["server_time_utc"].endswith("+00:00")
    assert response.headers["cache-control"] == "no-store"
