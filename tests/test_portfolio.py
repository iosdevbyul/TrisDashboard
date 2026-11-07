import json

import pytest

from backend.portfolio import load_portfolio, portfolio


def write_snapshot(tmp_path, positions, as_of=None):
    if as_of is None:
        from datetime import datetime, timezone, timedelta
        as_of = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    path = tmp_path / "holdings.json"
    path.write_text(json.dumps({"as_of": as_of, "positions": positions}))
    return path


def test_mixed_currencies_never_combined(tmp_path):
    path = write_snapshot(tmp_path, [
        {"symbol": "JEPQ", "currency": "USD", "quantity": 2, "price": 50},
        {"symbol": "TEST", "currency": "KRW", "quantity": 3, "price": 1000},
    ])
    result = load_portfolio(path)
    assert result["totals"] == {"KRW": "3000", "USD": "100"}
    assert result["valuation_complete"]


def test_missing_price_is_not_invented(tmp_path):
    path = write_snapshot(tmp_path, [
        {"symbol": "SCHD", "currency": "USD", "quantity": 3},
    ])
    result = load_portfolio(path)
    assert result["positions"][0]["market_value"] is None
    assert result["totals"] == {}
    assert not result["valuation_complete"]


@pytest.mark.parametrize("quantity", [-1, "NaN", "Infinity", True, "bad"])
def test_invalid_quantity_rejected(tmp_path, quantity):
    path = write_snapshot(tmp_path, [
        {"symbol": "JEPQ", "currency": "USD", "quantity": quantity},
    ])
    with pytest.raises(ValueError):
        load_portfolio(path)


def test_invalid_snapshot_does_not_crash_dashboard(tmp_path, monkeypatch):
    path = tmp_path / "holdings.json"
    path.write_text("{bad json")
    monkeypatch.setenv("TRIS_PORTFOLIO_FILE", str(path))
    assert portfolio() == {"available": False, "configured": True, "stale": True}


def test_portfolio_unconfigured(monkeypatch):
    monkeypatch.delenv("TRIS_PORTFOLIO_FILE", raising=False)
    assert not portfolio()["available"]


def test_snapshot_age_metadata(tmp_path):
    from datetime import datetime, timezone
    from backend.quality import snapshot_quality
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    path = write_snapshot(tmp_path, [{"symbol": "QQQI", "currency": "USD", "quantity": "3"}],
                          as_of=(now - timedelta(days=5)).isoformat())
    data = load_portfolio(path)
    assert data["quality"]["outdated"] is True
    assert data["quality"]["threshold_hours"] == 72
