import json
from datetime import date
from backend.dividends import load_dividends


def write_payments(tmp_path, payments):
    path = tmp_path / "dividends.json"
    path.write_text(json.dumps({"payments": payments}), encoding="utf-8")
    return path


def test_first_calendar_month_does_not_show_year_zero(tmp_path):
    path = write_payments(tmp_path, [{"symbol": "JEPQ", "currency": "USD",
        "amount": "10", "paid_on": "0001-01-01"}])
    result = load_dividends(path, today=date(1, 1, 1))
    assert [entry["month"] for entry in result["history"]] == ["0001-01"]
    assert result["observed_monthly_average"] == {"USD": "10.00"}
    assert result["completed_month_change"] == {}


def test_early_calendar_history_uses_only_existing_months(tmp_path):
    path = write_payments(tmp_path, [
        {"symbol": "JEPQ", "currency": "USD", "amount": "10", "paid_on": "0001-01-01"},
        {"symbol": "JEPQ", "currency": "USD", "amount": "20", "paid_on": "0001-02-01"},
    ])
    result = load_dividends(path, today=date(1, 3, 1))
    assert [entry["month"] for entry in result["history"]] == ["0001-01", "0001-02", "0001-03"]
    assert result["completed_month_average"] == {"USD": "15.00"}
    assert result["observed_monthly_average"] == {"USD": "10.00"}
    assert result["completed_month_change"]["USD"]["difference"] == "10"
