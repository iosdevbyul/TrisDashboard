import pytest
from backend.access import allowed_client, validate_allowlist
from fastapi.testclient import TestClient
from backend.app import app


def test_default_is_backward_compatible(monkeypatch):
    monkeypatch.delenv("TRIS_ALLOWED_CLIENT_IPS", raising=False)
    assert allowed_client("192.168.0.12")
    assert allowed_client("testclient")


def test_exact_ip_and_cidr():
    assert allowed_client("192.168.1.42", "127.0.0.1,192.168.1.0/24")
    assert not allowed_client("192.168.2.10", "127.0.0.1,192.168.1.0/24")
    assert allowed_client("::ffff:192.168.1.42", "192.168.1.0/24")
    assert allowed_client("fd12::12", "fd12::/64")
    assert not allowed_client("testclient", "192.168.1.0/24")


@pytest.mark.parametrize("value", ["", "not-an-ip", "1.2.3.4/99", ",127.0.0.1", "127.0.0.1,"])
def test_invalid_policy_rejected(value):
    with pytest.raises(ValueError):
        validate_allowlist(value)


def test_api_denies_unallowed_client(monkeypatch):
    monkeypatch.setenv("TRIS_ALLOWED_CLIENT_IPS", "127.0.0.1/32")
    response = TestClient(app).get("/healthz", headers={"X-Forwarded-For": "127.0.0.1"})
    assert response.status_code == 403
    assert response.text == "Forbidden"
