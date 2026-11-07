from fastapi.testclient import TestClient
from backend.app import app

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


def test_static_assets():
    for path in ("/static/style.css", "/static/dashboard.js"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.content
