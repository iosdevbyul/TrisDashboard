import json
from datetime import datetime, timezone, timedelta

from macos.preflight import inspect_settings


def write_settings(tmp_path, **entries):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(entries))
    return path


def test_valid_and_missing_optional_sources(tmp_path):
    portfolio = tmp_path / "holdings.json"
    portfolio.write_text(json.dumps({
        "as_of": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
        "positions": [{"symbol": "TEST", "currency": "USD", "quantity": 1}],
    }))
    result = inspect_settings(write_settings(tmp_path, TRIS_PORTFOLIO_FILE=str(portfolio)))
    assert result["ready"] is True
    assert result["files"]["portfolio"] == "valid"
    assert result["files"]["fitness"] == "not-configured"


def test_missing_private_file_fails_without_printing_path(tmp_path):
    missing = str(tmp_path / "a-very-private-file.json")
    result = inspect_settings(write_settings(tmp_path, TRIS_AGENDA_FILE=missing))
    assert result["ready"] is False
    assert result["files"]["agenda"] == "invalid"
    assert missing not in str(result)


def test_invalid_settings_does_not_leak_secrets(tmp_path):
    path = write_settings(tmp_path, GITHUB_TOKEN="a-secret-that-must-not-appear")
    result = inspect_settings(path)
    assert result == {"settings": "invalid", "files": {}, "ready": False}
    assert "a-secret" not in str(result)


def test_empty_settings_allow_deferred_data_configuration(tmp_path):
    assert inspect_settings(write_settings(tmp_path))["ready"]
