import json
from datetime import date
import pytest
from backend.dividends import dividends, load_dividends

def snapshot(tmp_path, payments):
    path = tmp_path / "payments.json"
    path.write_text(json.dumps({"payments": payments}))
    return path

def test_monthly_totals_do_not_convert_currencies(tmp_path):
    file = snapshot(tmp_path, [
        {"symbol": "JEPQ", "paid_on": "2026-11-04", "currency": "USD", "amount": "60.25"},
        {"symbol": "QQQI", "paid_on": "2026-11-05", "currency": "USD", "amount": "40.10"},
        {"symbol": "KR", "paid_on": "2026-11-06", "currency": "KRW", "amount": "9000"},
        {"symbol": "SCHD", "paid_on": "2026-10-01", "currency": "USD", "amount": "12"},
    ])
    result = load_dividends(file, today=date(2026, 11, 8))
    assert result["monthly_totals"] == {"KRW": "9000", "USD": "100.35"}
    assert result["record_count"] == 4
    assert result["recent"][0]["symbol"] == "KR"

@pytest.mark.parametrize("amount", ["NaN", "-1", True, "Infinity"])
def test_invalid_payments_rejected(tmp_path, amount):
    file = snapshot(tmp_path, [{"symbol": "JEPQ", "paid_on": "2026-11-01", "currency": "USD", "amount": amount}])
    with pytest.raises(ValueError):
        load_dividends(file, today=date(2026, 11, 8))

def test_future_payment_not_counted_as_confirmed(tmp_path):
    file = snapshot(tmp_path, [{"symbol": "JEPQ", "paid_on": "2026-12-01", "currency": "USD", "amount": "10"}])
    with pytest.raises(ValueError):
        load_dividends(file, today=date(2026, 11, 8))

def test_unconfigured(monkeypatch):
    monkeypatch.delenv("TRIS_DIVIDENDS_FILE", raising=False)
    assert dividends()["configured"] is False
