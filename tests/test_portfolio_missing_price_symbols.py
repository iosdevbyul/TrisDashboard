import json
from datetime import datetime, timezone
from backend.portfolio import load_portfolio


def data(tmp_path, positions):
    path = tmp_path / "portfolio.json"
    path.write_text(json.dumps({
        "as_of": datetime.now(timezone.utc).isoformat(),
        "positions": positions,
    }), encoding="utf-8")
    return load_portfolio(path)


def test_missing_symbols_sorted_by_currency_and_symbol(tmp_path):
    positions = [
        {"symbol": "qqqi", "currency": "USD", "quantity": "1"},
        {"symbol": "SCHD", "currency": "USD", "quantity": "3", "price": "26"},
        {"symbol": "JEPQ", "currency": "USD", "quantity": "5"},
        {"symbol": "005930", "currency": "KRW", "quantity": "2"},
    ]
    result = data(tmp_path, positions)
    assert result["unpriced_symbols_by_currency"] == {
        "KRW": ["005930"], "USD": ["JEPQ", "QQQI"]}
    assert result["unpriced_positions_by_currency"] == {"KRW": 1, "USD": 2}


def test_no_missing_prices_has_no_symbols(tmp_path):
    assert data(tmp_path, [{"symbol": "JEPQ", "currency": "USD", "quantity": 1, "price": 50}])["unpriced_symbols_by_currency"] == {}
