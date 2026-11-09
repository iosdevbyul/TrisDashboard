import pytest
from backend import integrations


@pytest.mark.parametrize("current", [
    {"temperature_2m": float("nan"), "relative_humidity_2m": 40, "weather_code": 1},
    {"temperature_2m": 20, "relative_humidity_2m": 150, "weather_code": 1},
    {"temperature_2m": 20, "relative_humidity_2m": 40, "weather_code": True},
    {"temperature_2m": 20, "relative_humidity_2m": 40, "weather_code": 100},
])
def test_invalid_mandatory_weather_fields_are_unavailable(monkeypatch, current):
    integrations._cache.clear()
    monkeypatch.setattr(integrations, "get_json", lambda url: {"current": current})
    value = integrations.weather()
    assert value["available"] is False
    assert value["stale"] is True


def test_invalid_optional_weather_fields_are_omitted(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setattr(integrations, "get_json", lambda url: {"current": {
        "temperature_2m": 20, "relative_humidity_2m": 40, "weather_code": 1,
        "apparent_temperature": float("nan"), "wind_speed_10m": -3,
    }})
    value = integrations.weather()
    assert value["available"] is True
    assert value["feels_like_c"] is None
    assert value["wind_kmh"] is None
