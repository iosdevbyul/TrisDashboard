import json
from datetime import date
from backend.dividends import load_dividends


def load(tmp_path, payments):
    path = tmp_path / "dividends.json"
    path.write_text(json.dumps({"payments": payments}), encoding="utf-8")
    return load_dividends(path, today=date(2026, 11, 9))


def test_current_month_payment_count_includes_multiple_same_symbol_payments(tmp_path):
    data = load(tmp_path, [
        {"symbol": "JEPQ", "currency": "USD", "paid_on": "2026-11-01", "amount": "12"},
        {"symbol": "JEPQ", "currency": "USD", "paid_on": "2026-11-08", "amount": "13"},
        {"symbol": "SCHD", "currency": "USD", "paid_on": "2026-10-31", "amount": "5"},
        {"symbol": "KR", "currency": "KRW", "paid_on": "2026-11-09", "amount": "20"},
    ])
    assert data["monthly_payment_counts"] == {"KRW": 1, "USD": 2}
    assert data["monthly_totals"] == {"KRW": "20", "USD": "25"}


def test_no_current_payments_has_empty_counts(tmp_path):
    assert load(tmp_path, [])["monthly_payment_counts"] == {}
