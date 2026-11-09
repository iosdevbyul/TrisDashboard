import pytest
from backend import integrations


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _):
        return self.body


@pytest.mark.parametrize("body", [
    b'{"current":{"temperature_2m":10,"temperature_2m":100}}',
    b'{"current":{"temperature_2m":NaN}}',
    b'{"current":{"temperature_2m":Infinity}}',
])
def test_provider_json_rejects_duplicate_keys_and_nonstandard_numbers(monkeypatch, body):
    monkeypatch.setattr(integrations, "urlopen", lambda *_args, **_kwargs: FakeResponse(body))
    with pytest.raises(ValueError):
        integrations.get_json("https://example.invalid/weather")


def test_provider_json_valid_object_is_accepted(monkeypatch):
    monkeypatch.setattr(integrations, "urlopen", lambda *_args, **_kwargs: FakeResponse(b'{"current":{"temperature_2m":10}}'))
    assert integrations.get_json("https://example.invalid/weather") == {"current": {"temperature_2m": 10}}
