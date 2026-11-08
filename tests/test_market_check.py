import json
from macos.market_check import inspect_market
from macos.secure_launch import SERVICE_NAMES


def write_settings(tmp_path, **settings):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(settings))
    return path


def test_market_readiness_without_api_calls_or_leaking_credentials(tmp_path):
    requested = []
    def lookup(service):
        requested.append(service)
        return "private-credential"
    result = inspect_market(
        write_settings(tmp_path, TRIS_QUOTE_SYMBOLS="JEPQ,QQQI"), lookup=lookup
    )
    assert result == {
        "settings_valid": True, "symbols_configured": True,
        "symbol_count": 2, "keychain_key_present": True,
        "ready_for_optional_api_test": True, "network_requests": 0,
    }
    assert requested == [SERVICE_NAMES["TRIS_TWELVEDATA_API_KEY"]]
    assert "private-credential" not in str(result)
    assert "JEPQ" not in str(result)


def test_market_preflight_missing_key_remains_optional(tmp_path):
    result = inspect_market(
        write_settings(tmp_path, TRIS_QUOTE_SYMBOLS="JEPQ"),
        lookup=lambda service: None,
    )
    assert result["ready_for_optional_api_test"] is False
    assert result["settings_valid"] is True


def test_market_preflight_invalid_settings_sanitized(tmp_path):
    result = inspect_market(write_settings(tmp_path, TRIS_TWELVEDATA_API_KEY="secret"),
                            lookup=lambda service: "secret")
    assert result["settings_valid"] is False
    assert "secret" not in str(result)


def test_market_preflight_keychain_error_is_not_fatal(tmp_path):
    def unavailable(service):
        raise OSError("sensitive-keychain-path")
    result = inspect_market(write_settings(tmp_path, TRIS_QUOTE_SYMBOLS="JEPQ"),
                            lookup=unavailable)
    assert result["keychain_key_present"] is False
    assert "sensitive-keychain-path" not in str(result)


def test_market_preflight_without_symbols_does_not_touch_keychain(tmp_path):
    def forbidden_lookup(service):
        raise AssertionError("Unconfigured market data must not access Keychain")
    report = inspect_market(write_settings(tmp_path), lookup=forbidden_lookup)
    assert report["settings_valid"] is True
    assert report["symbols_configured"] is False
    assert report["keychain_key_present"] is False
    assert report["network_requests"] == 0


def test_configured_symbols_still_check_keychain(tmp_path):
    calls = []
    def lookup(service):
        calls.append(service)
        return "present"
    report = inspect_market(write_settings(tmp_path, TRIS_QUOTE_SYMBOLS="JEPQ"), lookup=lookup)
    assert report["ready_for_optional_api_test"] is True
    assert calls == [SERVICE_NAMES["TRIS_TWELVEDATA_API_KEY"]]


def test_market_preflight_rejects_malformed_keychain_lookup_without_leaking(tmp_path):
    for exception in (ValueError("private-key"), TypeError("private-key")):
        def failing_lookup(service):
            raise exception
        report = inspect_market(write_settings(tmp_path, TRIS_QUOTE_SYMBOLS="JEPQ"),
                                lookup=failing_lookup)
        assert report["settings_valid"] is True
        assert report["keychain_key_present"] is False
        assert report["ready_for_optional_api_test"] is False
        assert "private-key" not in str(report)


import pytest


@pytest.mark.parametrize("credential", [True, 123, ["secret"], {}, "  "])
def test_market_preflight_rejects_noncredential_keychain_results(tmp_path, credential):
    report = inspect_market(write_settings(tmp_path, TRIS_QUOTE_SYMBOLS="JEPQ"),
                            lookup=lambda service: credential)
    assert report["keychain_key_present"] is False
    assert report["ready_for_optional_api_test"] is False
    assert set(report) == {"settings_valid", "symbols_configured", "symbol_count",
                           "keychain_key_present", "ready_for_optional_api_test",
                           "network_requests"}
