import json
from datetime import datetime, timezone, date
import pytest
from backend.portfolio import load_portfolio, portfolio
from backend.dividends import load_dividends


@pytest.mark.parametrize("field", ["quantity", "price"])
def test_extreme_manual_portfolio_values_rejected(tmp_path, field):
    path = tmp_path / "portfolio.json"
    holding = {"symbol": "JEPQ", "currency": "USD", "quantity": "2", "price": "50"}
    holding[field] = "1e999999999"
    path.write_text(json.dumps({"as_of": datetime.now(timezone.utc).isoformat(), "positions": [holding]}))
    with pytest.raises(ValueError):
        load_portfolio(path)


def test_extreme_dividend_amount_rejected_without_decimal_overflow(tmp_path):
    path = tmp_path / "dividends.json"
    path.write_text(json.dumps({"payments": [{"symbol": "JEPQ", "currency": "USD",
        "amount": "1e999999999", "paid_on": "2026-11-01"}]}))
    with pytest.raises(ValueError):
        load_dividends(path, today=date(2026, 11, 9))
