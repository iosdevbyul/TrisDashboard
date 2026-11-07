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


def test_six_month_payment_history_is_currency_separated(tmp_path):
    source = snapshot(tmp_path, [
        {"symbol": "JEPQ", "paid_on": "2026-11-04", "currency": "USD", "amount": "50.25"},
        {"symbol": "QQQI", "paid_on": "2026-11-05", "currency": "USD", "amount": "15.75"},
        {"symbol": "KRETF", "paid_on": "2026-10-06", "currency": "KRW", "amount": "2000"},
        {"symbol": "OLD", "paid_on": "2026-04-10", "currency": "USD", "amount": "500"},
    ])
    data = load_dividends(source, today=date(2026, 11, 8))
    history = data["history"]
    assert len(history) == 6
    assert history[0]["month"] == "2026-06"
    assert history[-1] == {"month": "2026-11", "totals": {"USD": "66.00"}}
    assert history[-2] == {"month": "2026-10", "totals": {"KRW": "2000"}}


def test_six_month_history_crosses_new_year(tmp_path):
    data = load_dividends(snapshot(tmp_path, []), today=date(2026, 2, 4))
    assert [item["month"] for item in data["history"]] == [
        "2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02"]
