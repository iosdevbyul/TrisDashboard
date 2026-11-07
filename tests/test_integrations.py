from backend import integrations


def test_weather_mapped_and_cached(monkeypatch):
    integrations._cache.clear()
    calls = []
    def fake_get(url):
        calls.append(url)
        return {"current": {"temperature_2m": 12.5, "relative_humidity_2m": 48, "weather_code": 3}}
    monkeypatch.setattr(integrations, "get_json", fake_get)
    data = integrations.weather()
    assert data["temperature_c"] == 12.5
    assert data["available"] and data["stale"] is False
    assert integrations.weather() == data
    assert len(calls) == 1


def test_weather_stale_fallback(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setattr(integrations, "get_json", lambda url: {"current": {"temperature_2m": 10, "relative_humidity_2m": 30, "weather_code": 1}})
    assert integrations.weather()["available"]
    for item in integrations._cache.values():
        item["time"] = -999999
    def fail(url):
        raise OSError("no network")
    monkeypatch.setattr(integrations, "get_json", fail)
    stale = integrations.weather()
    assert stale["available"] and stale["stale"]


def test_github_repositories(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setenv("TRIS_GITHUB_REPOS", "iosdevbyul/TrisDashboard,iosdevbyul/TrisDashboard")
    def mock_github(url):
        if "/actions/runs" in url:
            return {"workflow_runs": [{"status": "completed", "conclusion": "success", "html_url": "https://github.com/iosdevbyul/TrisDashboard/actions/runs/42", "name": "CI"}]}
        return [{"number": 2, "title": "Fix tests", "html_url": "https://github.com/iosdevbyul/TrisDashboard/pull/2"}]
    monkeypatch.setattr(integrations, "get_json", mock_github)
    result = integrations.github()
    assert len(result["repositories"]) == 1
    assert result["repositories"][0]["open_pr_count"] == 1
    assert result["repositories"][0]["latest_ci"]["conclusion"] == "success"


def test_unavailable_no_credentials_or_errors_leaked(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setattr(integrations, "get_json", lambda url: (_ for _ in ()).throw(OSError("secret details")))
    result = integrations.weather()
    assert result == {"available": False, "stale": True, "error": "temporarily unavailable"}


def test_trello_not_configured(monkeypatch):
    integrations._cache.clear()
    monkeypatch.delenv("TRIS_TRELLO_BOARD_ID", raising=False)
    assert integrations.trello() == {"available": False, "configured": False, "stale": False}


def test_trello_board_lists_and_private_credentials(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setenv("TRIS_TRELLO_BOARD_ID", "abc123")
    monkeypatch.setenv("TRIS_TRELLO_KEY", "privatekey")
    monkeypatch.setenv("TRIS_TRELLO_TOKEN", "privatetoken")
    calls = []
    def fake_get(url):
        calls.append(url)
        return [
            {"name": "Next", "cards": [{"name": "Feature A"}, {"name": "Feature B"}]},
            {"name": "In Progress", "cards": [{"name": "Feature C"}]},
            {"name": "Done", "cards": []},
            {"name": "Other", "cards": [{"name": "Ignore"}]},
        ]
    monkeypatch.setattr(integrations, "get_json", fake_get)
    data = integrations.trello()
    assert data["available"] and data["configured"]
    assert [value["count"] for value in data["lists"]] == [2, 1, 0]
    assert "privatetoken" in calls[0]
    assert "privatetoken" not in str(data)
    assert "privatetoken" not in str(integrations._cache)
    assert integrations.trello() == data
    assert len(calls) == 1


def test_trello_stale_if_provider_unavailable(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setenv("TRIS_TRELLO_BOARD_ID", "abc123")
    monkeypatch.setenv("TRIS_TRELLO_KEY", "key")
    monkeypatch.setenv("TRIS_TRELLO_TOKEN", "token")
    monkeypatch.setattr(integrations, "get_json", lambda url: [{"name": "Next", "cards": []}])
    assert integrations.trello()["available"]
    for item in integrations._cache.values():
        item["time"] = -999999
    monkeypatch.setattr(integrations, "get_json", lambda url: (_ for _ in ()).throw(OSError("offline")))
    assert integrations.trello()["stale"]


def test_extended_weather_fields(monkeypatch):
    integrations._cache.clear()
    def response(url):
        assert "daily=" in url
        return {
            "current": {
                "temperature_2m": 16,
                "relative_humidity_2m": 60,
                "weather_code": 2,
                "apparent_temperature": 14,
                "wind_speed_10m": 8,
            },
            "daily": {
                "temperature_2m_max": [20],
                "temperature_2m_min": [11],
                "precipitation_probability_max": [35],
            },
        }
    monkeypatch.setattr(integrations, "get_json", response)
    data = integrations.weather()
    assert data["feels_like_c"] == 14
    assert data["today_high_c"] == 20
    assert data["today_low_c"] == 11
    assert data["rain_chance_percent"] == 35
