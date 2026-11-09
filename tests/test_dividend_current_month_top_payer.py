import json
from datetime import date
from backend.dividends import load_dividends


def read(tmp_path, payments):
    p = tmp_path / "dividends.json"
    p.write_text(json.dumps({"payments": payments}), encoding="utf-8")
    return load_dividends(p, today=date(2026, 11, 9))


def payment(symbol, paid, amount, currency="USD"):
    return {"symbol": symbol, "currency": currency, "paid_on": paid, "amount": amount}


def test_current_month_top_payer_aggregates_same_symbol_and_separates_currency(tmp_path):
    data = read(tmp_path, [
        payment("qqqi", "2026-11-01", "8"),
        payment("QQQI", "2026-11-02", "7"),
        payment("JEPQ", "2026-11-05", "12"),
        payment("BIG", "2026-10-30", "999"),
        payment("KR", "2026-11-08", "1000", "KRW"),
    ])
    assert data["monthly_top_payers"] == {
        "USD": {"symbol": "QQQI", "amount": "15"},
        "KRW": {"symbol": "KR", "amount": "1000"}}


def test_empty_month_has_no_top_payers(tmp_path):
    assert read(tmp_path, [payment("JEPQ", "2026-10-01", "5")])["monthly_top_payers"] == {}
