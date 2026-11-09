import json
from datetime import datetime, timezone
from backend.portfolio import load_portfolio


def load(tmp_path, positions):
    path = tmp_path / "holdings.json"
    path.write_text(json.dumps({"as_of": datetime.now(timezone.utc).isoformat(),
                                "positions": positions}), encoding="utf-8")
    return load_portfolio(path)


def test_missing_manual_prices_counted_per_currency(tmp_path):
    data = load(tmp_path, [
        {"symbol": "JEPQ", "currency": "USD", "quantity": "1"},
        {"symbol": "QQQI", "currency": "USD", "quantity": "2"},
        {"symbol": "SCHD", "currency": "USD", "quantity": "3", "price": "20"},
        {"symbol": "KRX", "currency": "KRW", "quantity": "1"},
    ])
    assert data["unpriced_positions_by_currency"] == {"KRW": 1, "USD": 2}
    assert data["valuation_complete"] is False


def test_all_priced_positions_produce_no_missing_price_warning(tmp_path):
    data = load(tmp_path, [{"symbol": "JEPQ", "currency": "USD", "quantity": 1, "price": 40}])
    assert data["unpriced_positions_by_currency"] == {}
