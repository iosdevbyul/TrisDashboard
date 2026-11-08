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


@pytest.mark.parametrize("paid_on", ["20261108", "2026-11-8", "2026-02-30", 20261108, None, "２０２６-11-08"])
def test_reject_noncanonical_payment_date(tmp_path, paid_on):
    source = snapshot(tmp_path, [{"symbol": "JEPQ", "currency": "USD",
                                  "paid_on": paid_on, "amount": "1"}])
    with pytest.raises(ValueError):
        load_dividends(source, today=date(2026, 11, 8))


def test_reject_ambiguous_duplicate_payment_keys(tmp_path):
    source = tmp_path / "dividends.json"
    source.write_text('{"payments":[{"symbol":"JEPQ","currency":"USD","paid_on":"2026-11-01","amount":"1","amount":"99"}]}')
    with pytest.raises(ValueError, match="Duplicate"):
        load_dividends(source, today=date(2026, 11, 8))


def test_reject_unicode_ticker_confusable(tmp_path):
    source = snapshot(tmp_path, [{"symbol": "ＪＥＰＱ", "currency": "USD",
                                  "paid_on": "2026-11-01", "amount": "1"}])
    with pytest.raises(ValueError):
        load_dividends(source, today=date(2026, 11, 8))


def test_invalid_dividends_fall_back_without_crash(tmp_path, monkeypatch):
    source = snapshot(tmp_path, [{"symbol": "JEPQ", "currency": "USD",
                                  "paid_on": "20261101", "amount": "1"}])
    monkeypatch.setenv("TRIS_DIVIDENDS_FILE", str(source))
    assert dividends() == {"available": False, "configured": True, "stale": True}


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_reject_nonstandard_json_numeric_constant_anywhere(tmp_path, constant):
    path = tmp_path / "invalid-dividends.json"
    path.write_text('{"metadata":' + constant + ',"payments":[]}')
    with pytest.raises(ValueError, match="Non-standard JSON"):
        load_dividends(path, today=date(2026, 11, 8))


@pytest.mark.parametrize("reference", ["2026-11-08", 1, True, __import__("datetime").datetime(2026, 11, 8)])
def test_invalid_dividend_reference_date_is_rejected(tmp_path, reference):
    with pytest.raises(ValueError, match="Invalid dividend reference date"):
        load_dividends(snapshot(tmp_path, []), today=reference)


def test_six_month_dividend_totals_exclude_older_payments(tmp_path):
    from datetime import date
    import json
    from backend.dividends import load_dividends
    path = tmp_path / "payments.json"
    path.write_text(json.dumps({"payments": [
        {"symbol": "JEPQ", "currency": "USD", "amount": "10.25", "paid_on": "2026-11-01"},
        {"symbol": "SCHD", "currency": "USD", "amount": "5.75", "paid_on": "2026-06-01"},
        {"symbol": "QQQI", "currency": "USD", "amount": "100", "paid_on": "2026-04-01"}
    ]}))
    data = load_dividends(path, today=date(2026, 11, 8))
    assert data["six_month_totals"] == {"USD": "16.00"}
    assert data["monthly_totals"] == {"USD": "10.25"}
