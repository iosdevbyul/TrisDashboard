from backend import integrations


def test_invalid_optional_forecast_values_are_omitted(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setattr(integrations, "get_json", lambda url: {
        "current": {"temperature_2m": 10, "relative_humidity_2m": 40, "weather_code": 2},
        "daily": {"temperature_2m_max": [1000], "temperature_2m_min": [-200],
                  "precipitation_probability_max": [150]},
    })
    result = integrations.weather()
    assert result["available"] is True
    assert result["today_high_c"] is None
    assert result["today_low_c"] is None
    assert result["rain_chance_percent"] is None


def test_valid_optional_forecasts_remain_available(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setattr(integrations, "get_json", lambda url: {
        "current": {"temperature_2m": 10, "relative_humidity_2m": 40, "weather_code": 2},
        "daily": {"temperature_2m_max": [15], "temperature_2m_min": [5],
                  "precipitation_probability_max": [65]},
    })
    result = integrations.weather()
    assert (result["today_high_c"], result["today_low_c"], result["rain_chance_percent"]) == (15, 5, 65)
