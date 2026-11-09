import json
from datetime import date
import pytest
from backend.dividends import load_dividends, dividends


def file_with(tmp_path, amount):
    path = tmp_path / "dividends.json"
    path.write_text(json.dumps({"payments": [
        {"symbol": "JEPQ", "currency": "USD", "paid_on": "2026-10-01", "amount": amount},
        {"symbol": "JEPQ", "currency": "USD", "paid_on": "2026-11-01", "amount": "10"}
    ]}), encoding="utf-8")
    return path


def test_extreme_tiny_dividend_does_not_overflow_growth_calculation(tmp_path):
    with pytest.raises(ValueError, match="supported range"):
        load_dividends(file_with(tmp_path, "1e-999"), today=date(2026, 11, 9))


def test_normal_fractional_dividend_still_supported(tmp_path):
    data = load_dividends(file_with(tmp_path, "0.125"), today=date(2026, 11, 9))
    assert data["monthly_totals"] == {"USD": "10"}


def test_wrapper_rejects_tiny_dividend_safely(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIS_DIVIDENDS_FILE", str(file_with(tmp_path, "1e-999")))
    assert dividends() == {"available": False, "configured": True, "stale": True}
