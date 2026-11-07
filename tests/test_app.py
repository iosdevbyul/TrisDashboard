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


def test_display_settings_and_legacy_preferences_script():
    html = client.get("/").text
    assert 'id="display-settings"' in html
    assert 'data-panel="portfolio"' in html
    assert 'data-panel="fitness"' in html
    script = client.get("/static/preferences.js")
    assert script.status_code == 200
    assert "localStorage" in script.text
    for forbidden in ("const ", "let ", "=>", "?.", "??", "fetch("):
        assert forbidden not in script.text


def test_glance_mode_markup_and_legacy_syntax():
    page = client.get("/").text
    assert 'id="glance-sources"' in page
    assert 'id="setting-glance"' in page
    settings = client.get("/static/preferences.js").text
    dashboard = client.get("/static/dashboard.js").text
    assert "glance" in settings
    assert "showSummary(payload)" in dashboard
    for script in (settings, dashboard):
        for unsupported in ("const ", "let ", "=>", "?.", "??", "fetch("):
            assert unsupported not in script


def test_frontend_retries_failed_overview_without_discarding_cards():
    page = client.get("/").text
    script = client.get("/static/dashboard.js").text
    assert 'id="data-refresh-state"' in page
    assert "consecutiveOverviewFailures" in script
    assert "retryOverview()" in script
    assert "clearOverviewRetry()" in script
    assert "30000, 60000, 120000, 180000" in script
    for token in ("const ", "let ", "=>", "fetch(", "?.", "??"):
        assert token not in script


def test_source_strip_covers_all_configured_panels():
    js = client.get("/static/dashboard.js").text
    assert '["weather", "github", "trello", "portfolio", "fitness", "dividends", "agenda"]' in js
    assert 'active + "/" + names.length + " ready"' in js
    assert "info.quality.outdated" in js
    assert '"/5 ready"' not in js
