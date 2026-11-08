"""Offline API/frontend contract smoke tests with deterministic mocked data."""
import re

from fastapi.testclient import TestClient
from backend import app as app_module

client = TestClient(app_module.app)


def test_frontend_data_ids_exist_for_every_renderer(monkeypatch):
    monkeypatch.setattr(app_module, "overview", lambda: {
        "weather": {"available": False, "configured": False},
        "github": {"available": False, "configured": False},
        "trello": {"available": False, "configured": False},
        "portfolio": {"available": False, "configured": False},
        "fitness": {"available": False, "configured": False},
        "dividends": {"available": False, "configured": False},
        "agenda": {"available": False, "configured": False},
    })
    html = client.get("/").text
    js = client.get("/static/dashboard.js").text
    identifiers = re.findall(r'text\("([^"]+)"', js)
    for identifier in set(identifiers):
        assert 'id="' + identifier + '"' in html, identifier
    payload = client.get("/api/overview").json()
    assert payload["server"]["available"] is True
    assert all(name in payload for name in ("weather", "github", "trello",
                                            "portfolio", "fitness", "dividends", "agenda"))


def test_dashboard_asset_links_resolve():
    html = client.get("/").text
    assert client.get("/static/dashboard.js").status_code == 200
    assert client.get("/static/preferences.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200
    assert "https://" not in html


def test_show_all_panels_control_is_served_and_wired():
    html = client.get("/").text
    js = client.get("/static/preferences.js").text
    assert 'id="show-all-panels"' in html
    assert 'getElementById("show-all-panels").addEventListener("click"' in js
    assert "settings.hidden = [];" in js


def test_legacy_ipad_controls_have_touch_targets_and_keyboard_focus():
    css = client.get("/static/style.css").text
    assert "min-height:44px" in css
    assert "outline:3px solid #a7ccef" in css
    assert "overflow-wrap:break-word" in css
    js = client.get("/static/dashboard.js").text
    assert "=>" not in js
    assert "const " not in js
