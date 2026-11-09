import json
from datetime import datetime, timezone
import pytest
from backend.portfolio import load_portfolio, portfolio


def snapshot(tmp_path, quantity, price):
    path = tmp_path / "portfolio.json"
    path.write_text(json.dumps({"as_of": datetime.now(timezone.utc).isoformat(),
        "positions": [{"symbol": "JEPQ", "currency": "USD",
                       "quantity": quantity, "price": price}]}), encoding="utf-8")
    return path


@pytest.mark.parametrize("quantity,price", [
    ("1e999", "2"), ("2", "1e999"), ("1e21", "1"),
])
def test_extreme_portfolio_inputs_do_not_reach_decimal_valuation(tmp_path, quantity, price):
    with pytest.raises(ValueError, match="supported precision"):
        load_portfolio(snapshot(tmp_path, quantity, price))


def test_invalid_portfolio_is_reported_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIS_PORTFOLIO_FILE", str(snapshot(tmp_path, "1e999", "1e999")))
    assert portfolio() == {"available": False, "configured": True, "stale": True}


def test_normal_large_and_fractional_portfolio_values_remain_supported(tmp_path):
    result = load_portfolio(snapshot(tmp_path, "0.25", "1000000"))
    assert result["totals"] == {"USD": "250000.00"}
