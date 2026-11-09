import pytest
from backend import integrations


def configure(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setenv("TRIS_TRELLO_BOARD_ID", "abc123")
    monkeypatch.setenv("TRIS_TRELLO_KEY", "key")
    monkeypatch.setenv("TRIS_TRELLO_TOKEN", "token")


@pytest.mark.parametrize("payload", [[None], [{"name": 42, "cards": []}]])
def test_invalid_trello_list_fails_safely(monkeypatch, payload):
    configure(monkeypatch)
    monkeypatch.setattr(integrations, "get_json", lambda url: payload)
    result = integrations.trello()
    assert result["available"] is False
    assert result["stale"] is True


def test_malformed_trello_card_names_are_not_exposed(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(integrations, "get_json", lambda url: [
        {"name": "Next", "cards": [{"name": "Good"}, None, {"name": {"bad": "shape"}}]}
    ])
    result = integrations.trello()
    assert result["available"] is True
    assert result["lists"][0]["count"] == 3
    assert result["lists"][0]["cards"] == ["Good"]
