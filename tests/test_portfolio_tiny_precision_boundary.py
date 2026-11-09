import json
from datetime import datetime, timezone
import pytest
from backend.portfolio import load_portfolio, portfolio


def write(tmp_path, quantity, price):
    file = tmp_path / "portfolio.json"
    file.write_text(json.dumps({"as_of": datetime.now(timezone.utc).isoformat(), "positions": [
        {"symbol": "JEPQ", "currency": "USD", "quantity": quantity, "price": price}
    ]}), encoding="utf-8")
    return file


@pytest.mark.parametrize("quantity,price", [("1e-1000", "2"), ("2", "1e-1000")])
def test_extreme_small_portfolio_values_not_silently_rounded(tmp_path, quantity, price):
    with pytest.raises(ValueError, match="supported precision"):
        load_portfolio(write(tmp_path, quantity, price))


def test_normal_fractional_portfolio_still_valid(tmp_path):
    assert load_portfolio(write(tmp_path, "0.125", "40"))["totals"] == {"USD": "5.000"}


def test_wrapper_handles_tiny_input_without_exposing_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIS_PORTFOLIO_FILE", str(write(tmp_path, "1e-1000", "2")))
    assert portfolio() == {"available": False, "configured": True, "stale": True}
