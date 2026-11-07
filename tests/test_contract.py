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
