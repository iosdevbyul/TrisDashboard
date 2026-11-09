from backend import integrations


def test_nested_cache_readers_cannot_mutate_cached_payload():
    integrations._cache.clear()
    calls = []
    def loader():
        calls.append(1)
        return {"available": True, "rows": [{"values": [1, 2]}]}
    first = integrations.cached("nested-isolation-test", loader)
    first["rows"][0]["values"].append(3)
    second = integrations.cached("nested-isolation-test", loader)
    assert second["rows"][0]["values"] == [1, 2]
    assert len(calls) == 1


def test_nested_cache_loader_cannot_mutate_snapshot_after_return():
    integrations._cache.clear()
    source = {"available": True, "rows": [{"value": 5}]}
    integrations.cached("nested-source-test", lambda: source)
    source["rows"][0]["value"] = 99
    assert integrations.cached("nested-source-test", lambda: None)["rows"][0]["value"] == 5
