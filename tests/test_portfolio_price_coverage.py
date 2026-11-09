import json
from datetime import datetime, timezone
from backend.portfolio import load_portfolio


def test_price_coverage_counts_missing_prices_per_currency(tmp_path):
    path = tmp_path / "portfolio.json"
    path.write_text(json.dumps({"as_of": datetime.now(timezone.utc).isoformat(), "positions": [
        {"symbol":"JEPQ","currency":"USD","quantity":10,"price":50},
        {"symbol":"SCHD","currency":"USD","quantity":5},
        {"symbol":"005930","currency":"KRW","quantity":3,"price":50000},
    ]}), encoding="utf-8")
    result = load_portfolio(path)
    assert result["price_coverage_by_currency"] == {
        "KRW": {"priced": 1, "total": 1},
        "USD": {"priced": 1, "total": 2},
    }
