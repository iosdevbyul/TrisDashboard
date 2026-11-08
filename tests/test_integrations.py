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
        item["time"] -= 601
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


def test_github_partial_failure_keeps_other_repo(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setenv("TRIS_GITHUB_REPOS", "owner/good,owner/bad")
    def provider(url):
        if "owner/bad" in url:
            raise OSError("private-provider-failure")
        if "/actions/runs" in url:
            return {"workflow_runs": []}
        return [{"number": 17, "title": "Improve UI", "html_url": "https://github.com/owner/good/pull/17"}]
    monkeypatch.setattr(integrations, "get_json", provider)
    result = integrations.github()
    assert result["available"] and result["partial"]
    assert result["repositories"][0]["available"]
    assert result["repositories"][0]["open_prs"][0]["number"] == 17
    assert result["repositories"][1]["available"] is False
    assert result["repositories"][1]["open_pr_count"] is None
    assert "private-provider-failure" not in str(result)


def test_github_all_failed_returns_unavailable(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setenv("TRIS_GITHUB_REPOS", "owner/failing")
    monkeypatch.setattr(integrations, "get_json", lambda url: (_ for _ in ()).throw(OSError("down")))
    data = integrations.github()
    assert data["available"] is False
    assert data["stale"] is True


def test_trello_credential_rotation_does_not_reuse_cached_cards(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setenv("TRIS_TRELLO_BOARD_ID", "abc123")
    monkeypatch.setenv("TRIS_TRELLO_KEY", "key")
    monkeypatch.setenv("TRIS_TRELLO_TOKEN", "token-v1")
    calls = []
    def fake_provider(url):
        calls.append(url)
        return [{"name": "Next", "cards": [{"name": "task"}]}]
    monkeypatch.setattr(integrations, "get_json", fake_provider)
    assert integrations.trello()["available"]
    monkeypatch.setenv("TRIS_TRELLO_TOKEN", "token-v2")
    assert integrations.trello()["available"]
    assert len(calls) == 2
    assert "token-v1" not in str(integrations._cache)
    assert "token-v2" not in str(integrations._cache)


def test_trello_bounded_counts_are_not_misrepresented(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setenv("TRIS_TRELLO_BOARD_ID", "abc123")
    monkeypatch.setenv("TRIS_TRELLO_KEY", "key")
    monkeypatch.setenv("TRIS_TRELLO_TOKEN", "token")
    monkeypatch.setattr(integrations, "get_json", lambda url: [
        {"name": "Next", "cards": [{"name": "task"}] * 100},
        {"name": "Done", "cards": []},
    ])
    result = integrations.trello()
    assert result["lists"][0]["count"] == 100
    assert result["lists"][0]["count_truncated"] is True
    assert result["lists"][1]["count_truncated"] is False


def test_private_github_uses_server_only_bearer_token(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setenv("TRIS_GITHUB_REPOS", "owner/private-repo")
    monkeypatch.setenv("TRIS_GITHUB_TOKEN", "private-access-token")
    calls = []
    def fake_http(url, headers=None):
        calls.append((url, headers))
        if "/actions/runs" in url:
            return {"workflow_runs": []}
        return [{"number": 9, "title": "Review", "html_url": "https://github.com/owner/private-repo/pull/9"}]
    monkeypatch.setattr(integrations, "get_json", fake_http)
    result = integrations.github()
    assert result["available"]
    assert all("Bearer private-access-token" == headers["Authorization"] for _, headers in calls)
    assert "private-access-token" not in str(result)
    assert "private-access-token" not in str(integrations._cache)


def test_github_token_rotation_invalidates_cache(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setenv("TRIS_GITHUB_REPOS", "owner/private-repo")
    monkeypatch.setenv("TRIS_GITHUB_TOKEN", "token-one")
    requests = []
    def fake_http(url, headers=None):
        requests.append(headers)
        if "/actions/runs" in url:
            return {"workflow_runs": []}
        return []
    monkeypatch.setattr(integrations, "get_json", fake_http)
    assert integrations.github()["available"]
    monkeypatch.setenv("TRIS_GITHUB_TOKEN", "token-two")
    assert integrations.github()["available"]
    assert len(requests) == 4
    assert "token-one" not in str(integrations._cache)
    assert "token-two" not in str(integrations._cache)


import pytest


@pytest.mark.parametrize("latitude, longitude", [("invalid", "126.9"), ("NaN", "126.9"),
                                                   ("91", "126.9"), ("37", "181"),
                                                   ("Infinity", "126.9")])
def test_weather_bad_coordinate_configuration_fails_safe(monkeypatch, latitude, longitude):
    integrations._cache.clear()
    monkeypatch.setenv("TRIS_LATITUDE", latitude)
    monkeypatch.setenv("TRIS_LONGITUDE", longitude)
    monkeypatch.setattr(integrations, "get_json", lambda url: pytest.fail("unexpected request"))
    assert integrations.weather() == {"available": False, "configured": True, "stale": True}


def test_github_repository_config_rejects_unicode_homographs(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setenv("TRIS_GITHUB_REPOS", "owner/répō,owner/ｒｅｐｏ,valid/repo")
    observed = []
    def fake_get(url):
        observed.append(url)
        if "/actions/runs" in url:
            return {"workflow_runs": []}
        return []
    monkeypatch.setattr(integrations, "get_json", fake_get)
    data = integrations.github()
    assert data["available"] is True
    assert [entry["repository"] for entry in data["repositories"]] == ["valid/repo"]
    assert len(observed) == 2


def test_provider_json_caps_response_before_decoding(monkeypatch):
    from backend import integrations
    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, limit):
            assert limit == integrations.MAX_PROVIDER_RESPONSE_BYTES + 1
            return self.payload[:limit]
    monkeypatch.setattr(integrations, "urlopen", lambda req, timeout: FakeResponse(b" " * (integrations.MAX_PROVIDER_RESPONSE_BYTES + 1)))
    with pytest.raises(ValueError, match="too large"):
        integrations.get_json("https://example.invalid/test")
    monkeypatch.setattr(integrations, "urlopen", lambda req, timeout: FakeResponse(b'{"temperature": 12}'))
    assert integrations.get_json("https://example.invalid/test") == {"temperature": 12}


def test_weather_retains_current_conditions_if_optional_daily_is_malformed(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setattr(integrations, "get_json", lambda url: {
        "current": {"temperature_2m": 18, "relative_humidity_2m": 45, "weather_code": 1},
        "daily": {"temperature_2m_max": "bad-shape", "temperature_2m_min": [],
                  "precipitation_probability_max": [float("nan")]},
    })
    value = integrations.weather()
    assert value["available"] is True
    assert value["temperature_c"] == 18
    assert value["today_high_c"] is None
    assert value["today_low_c"] is None
    assert value["rain_chance_percent"] is None
    integrations._cache.clear()
    monkeypatch.setattr(integrations, "get_json", lambda url: {
        "current": {"temperature_2m": 12, "relative_humidity_2m": 55, "weather_code": 2},
        "daily": None,
    })
    assert integrations.weather()["available"] is True


def test_invalid_github_repository_configuration_is_unavailable(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setenv("TRIS_GITHUB_REPOS", "invalid,owner/space repo,")
    monkeypatch.setattr(integrations, "get_json", lambda url: pytest.fail("unexpected GitHub request"))
    assert integrations.github() == {"available": False, "configured": True, "stale": True}


def test_cache_does_not_serve_provider_data_older_than_one_day(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setattr(integrations.time, "monotonic", lambda: 500000.0)
    calls = []
    def get_data():
        calls.append(True)
        if len(calls) > 1:
            raise OSError("provider unavailable")
        return {"available": True, "temperature_c": 18}
    assert integrations.cached("weather:bounded", get_data, ttl=60)["available"] is True
    integrations._cache["weather:bounded"]["time"] -= integrations.MAX_STALE_SECONDS + 1
    stale = integrations.cached("weather:bounded", get_data, ttl=60)
    assert stale["available"] is False
    assert stale["stale"] is True
    assert stale["error"] == "temporarily unavailable"
    assert len(calls) == 2
    integrations._cache.clear()


def test_cache_can_retain_recent_snapshot_on_temporary_error(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setattr(integrations.time, "monotonic", lambda: 500000.0)
    assert integrations.cached("weather:recent", lambda: {"available": True}, ttl=60)["available"]
    integrations._cache["weather:recent"]["time"] -= 120
    def down():
        raise OSError("provider offline")
    restored = integrations.cached("weather:recent", down, ttl=60)
    assert restored["available"] is True and restored["stale"] is True
    integrations._cache.clear()


def test_provider_cache_does_not_mutate_loader_owned_response():
    integrations._cache.clear()
    upstream = {"available": True, "location": "Seoul"}
    result = integrations.cached("isolated-upstream-payload", lambda: upstream)
    assert result["available"] is True
    assert result["stale"] is False
    assert "updated_at" not in upstream
    assert "stale" not in upstream
    assert integrations.cached("isolated-upstream-payload", lambda: None)["available"] is True
    integrations._cache.clear()
