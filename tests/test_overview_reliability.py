import threading
import time

from backend import integrations


def test_slow_provider_does_not_block_other_modules(monkeypatch):
    blocker = threading.Event()
    monkeypatch.setattr(integrations, "weather", lambda: (blocker.wait(2), {"available": True})[1])
    monkeypatch.setattr(integrations, "github", lambda: {"available": True, "repositories": []})
    monkeypatch.setattr(integrations, "trello", lambda: {"available": False, "configured": False})
    monkeypatch.setattr(integrations, "portfolio", lambda: {"available": False})
    monkeypatch.setattr(integrations, "fitness", lambda: {"available": False})
    start = time.monotonic()
    try:
        result = integrations.overview(timeout_seconds=0.05)
        assert time.monotonic() - start < 1
        assert result["weather"]["stale"] is True
        assert result["github"]["available"] is True
        assert result["fitness"]["available"] is False
    finally:
        blocker.set()
        # Ensure this shared in-flight request finishes before the next test.
        integrations._PROVIDER_INFLIGHT["weather"].result(timeout=2)


def test_provider_exception_never_breaks_other_data(monkeypatch):
    monkeypatch.setattr(integrations, "weather", lambda: (_ for _ in ()).throw(RuntimeError("secret")))
    monkeypatch.setattr(integrations, "github", lambda: {"available": True})
    monkeypatch.setattr(integrations, "trello", lambda: {"available": False})
    monkeypatch.setattr(integrations, "portfolio", lambda: {"available": False})
    monkeypatch.setattr(integrations, "fitness", lambda: {"available": False})
    result = integrations.overview()
    assert result["weather"] == {"available": False, "configured": True, "stale": True}
    assert "secret" not in str(result)
