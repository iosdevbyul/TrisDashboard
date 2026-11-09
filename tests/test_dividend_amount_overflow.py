import json
from datetime import date
import pytest
from backend.dividends import load_dividends, dividends


def test_extreme_dividend_payment_fails_validation(tmp_path, monkeypatch):
    path = tmp_path / "payments.json"
    path.write_text(json.dumps({"payments": [
        {"symbol": "JEPQ", "currency": "USD", "paid_on": "2026-11-08", "amount": "1e1000"}
    ]}), encoding="utf-8")
    with pytest.raises(ValueError, match="supported range"):
        load_dividends(path, today=date(2026, 11, 9))
    monkeypatch.setenv("TRIS_DIVIDENDS_FILE", str(path))
    assert dividends() == {"available": False, "configured": True, "stale": True}


def test_normal_dividend_payment_still_works(tmp_path):
    path = tmp_path / "payments.json"
    path.write_text(json.dumps({"payments": [
        {"symbol": "JEPQ", "currency": "USD", "paid_on": "2026-11-08", "amount": "12.50"}
    ]}), encoding="utf-8")
    assert load_dividends(path, today=date(2026, 11, 9))["monthly_totals"] == {"USD": "12.50"}
