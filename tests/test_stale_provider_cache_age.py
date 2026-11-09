from backend import integrations


def test_stale_provider_cache_reports_elapsed_seconds_without_changing_fresh_snapshot(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setattr(integrations.time, "monotonic", lambda: 1000.0)
    fresh = integrations.cached("stale-age-test", lambda: {"available": True, "value": 7}, ttl=5)
    assert "cache_age_seconds" not in fresh
    monkeypatch.setattr(integrations.time, "monotonic", lambda: 1067.0)

    def unavailable():
        raise OSError("provider secret")

    fallback = integrations.cached("stale-age-test", unavailable, ttl=5)
    assert fallback["stale"] is True
    assert fallback["cache_age_seconds"] == 67
    assert fallback["value"] == 7
    assert "provider secret" not in str(fallback)
    assert "cache_age_seconds" not in integrations._cache["stale-age-test"]["data"]
    integrations._cache.clear()
