import json
from datetime import datetime, timezone
from backend.portfolio import load_portfolio


def write(tmp_path, positions):
    path = tmp_path / "portfolio.json"
    path.write_text(json.dumps({"as_of": datetime.now(timezone.utc).isoformat(),
                                "positions": positions}), encoding="utf-8")
    return path


def pos(symbol, currency, value):
    return {"symbol": symbol, "currency": currency, "quantity": "1", "price": str(value)}


def test_top_three_concentration_uses_exact_same_currency_totals(tmp_path):
    holdings = [pos("A", "USD", 40), pos("B", "USD", 30),
                pos("C", "USD", 20), pos("D", "USD", 10),
                pos("KR", "KRW", 100)]
    data = load_portfolio(write(tmp_path, holdings))
    assert data["top_three_concentration_percent"] == {"USD": "90.0", "KRW": "100.0"}


def test_concentration_is_not_claimed_for_incomplete_price_snapshots(tmp_path):
    data = load_portfolio(write(tmp_path, [
        pos("A", "USD", 50),
        {"symbol": "B", "currency": "USD", "quantity": "1"},
    ]))
    assert data["top_three_concentration_percent"] == {}


def test_zero_value_snapshot_does_not_divide_by_zero(tmp_path):
    data = load_portfolio(write(tmp_path, [pos("A", "USD", 0)]))
    assert data["top_three_concentration_percent"] == {}
