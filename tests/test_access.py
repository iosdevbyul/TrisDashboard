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


def test_invalid_later_allowlist_rule_never_grants_access():
    assert not allowed_client("192.168.1.42", "192.168.1.0/24,invalid-rule")
    assert not allowed_client("192.168.1.42", "192.168.1.0/24,192.168.1.1/99")


def test_valid_later_rule_still_matches():
    assert allowed_client("192.168.1.42", "127.0.0.1,192.168.1.0/24")


def test_invalid_allowlist_types_fail_closed():
    for policy in (123, ["127.0.0.1"]):
        assert allowed_client("127.0.0.1", policy) is False
    for value in (None, 123, ["127.0.0.1"]):
        with pytest.raises(ValueError, match="Invalid client allowlist"):
            validate_allowlist(value)
