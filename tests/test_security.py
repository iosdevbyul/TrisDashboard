from fastapi.testclient import TestClient
from backend import app as app_module

client = TestClient(app_module.app)


def test_no_cache_for_private_dashboard_and_api(monkeypatch):
    monkeypatch.setattr(app_module, "overview", lambda: {"weather": {}, "github": {}})
    for path in ("/", "/api/overview", "/healthz"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"
        csp = response.headers["content-security-policy"]
        assert "script-src 'self'" in csp
        assert "object-src 'none'" in csp


def test_static_assets_force_revalidation():
    for path in ("/static/dashboard.js", "/static/preferences.js", "/static/style.css"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache, max-age=0, must-revalidate"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_unused_framework_docs_and_unknown_endpoint():
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/unrecognized-endpoint").status_code == 404
