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
    monkeypatch.setattr(integrations, "get_json", lambda url: [{"number": 2, "title": "Fix tests", "html_url": "https://github.com/iosdevbyul/TrisDashboard/pull/2"}])
    result = integrations.github()
    assert len(result["repositories"]) == 1
    assert result["repositories"][0]["open_pr_count"] == 1


def test_unavailable_no_credentials_or_errors_leaked(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setattr(integrations, "get_json", lambda url: (_ for _ in ()).throw(OSError("secret details")))
    result = integrations.weather()
    assert result == {"available": False, "stale": True, "error": "temporarily unavailable"}
