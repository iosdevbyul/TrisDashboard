from backend import integrations


def test_inverted_high_low_forecast_is_omitted(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setattr(integrations, "get_json", lambda url: {
        "current": {"temperature_2m": 12, "relative_humidity_2m": 50, "weather_code": 2},
        "daily": {"temperature_2m_max": [5], "temperature_2m_min": [20],
                  "precipitation_probability_max": [40]},
    })
    value = integrations.weather()
    assert value["available"] is True
    assert value["today_high_c"] is None
    assert value["today_low_c"] is None
    assert value["rain_chance_percent"] == 40


def test_valid_high_low_forecast_preserved(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setattr(integrations, "get_json", lambda url: {
        "current": {"temperature_2m": 12, "relative_humidity_2m": 50, "weather_code": 2},
        "daily": {"temperature_2m_max": [20], "temperature_2m_min": [5]},
    })
    value = integrations.weather()
    assert (value["today_high_c"], value["today_low_c"]) == (20, 5)
