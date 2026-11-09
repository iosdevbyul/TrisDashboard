import json
from datetime import datetime, timezone
import pytest
from backend.portfolio import load_portfolio, portfolio


def make_file(tmp_path, quantity, price="10"):
    path = tmp_path / "holdings.json"
    path.write_text(json.dumps({"as_of": datetime.now(timezone.utc).isoformat(), "positions": [
        {"symbol": "JEPQ", "currency": "USD", "quantity": quantity, "price": price}
    ]}), encoding="utf-8")
    return path


@pytest.mark.parametrize("quantity,price", [
    ("1e-999999999", "2"),
    ("2", "1e-999999999"),
])
def test_extreme_tiny_manual_numbers_rejected_before_arithmetic(tmp_path, quantity, price):
    with pytest.raises(ValueError, match="supported precision"):
        load_portfolio(make_file(tmp_path, quantity, price))


def test_portfolio_wrapper_fails_safely_on_tiny_input(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIS_PORTFOLIO_FILE", str(make_file(tmp_path, "1e-999999999")))
    result = portfolio()
    assert result["available"] is False
    assert result["configured"] is True


def test_normal_fractional_quantity_remains_supported(tmp_path):
    result = load_portfolio(make_file(tmp_path, "0.125", "40"))
    assert result["totals"] == {"USD": "5.000"}
