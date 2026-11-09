import json
from datetime import date
from backend.dividends import load_dividends


def write(tmp_path, payments):
    path = tmp_path / "dividends.json"
    path.write_text(json.dumps({"payments": payments}), encoding="utf-8")
    return path


def payment(symbol, month, amount, currency="USD"):
    return {"symbol": symbol, "currency": currency,
            "paid_on": "2026-" + month + "-15", "amount": str(amount)}


def test_paying_holdings_and_month_coverage_are_currency_specific(tmp_path):
    payments = [payment("JEPQ", "09", 10), payment("JEPQ", "10", 20),
                payment("QQQI", "10", 5), payment("ETF", "11", 3, "KRW"),
                payment("OLD", "01", 4)]
    data = load_dividends(write(tmp_path, payments), today=date(2026, 11, 20))
    assert data["six_month_paying_symbols"] == {"KRW": 1, "USD": 2}
    assert data["six_month_paid_months"] == {"KRW": 1, "USD": 2}


def test_empty_dividend_history_has_no_misleading_coverage(tmp_path):
    data = load_dividends(write(tmp_path, []), today=date(2026, 11, 20))
    assert data["six_month_paying_symbols"] == {}
    assert data["six_month_paid_months"] == {}
