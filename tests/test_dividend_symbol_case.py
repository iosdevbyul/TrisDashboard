import json
from datetime import date
from backend.dividends import load_dividends


def test_dividend_symbol_grouping_is_case_insensitive(tmp_path):
    path = tmp_path / "dividends.json"
    path.write_text(json.dumps({"payments": [
        {"symbol": "jepq", "currency": "USD", "amount": "10", "paid_on": "2026-11-01"},
        {"symbol": "JEPQ", "currency": "USD", "amount": "5", "paid_on": "2026-10-01"},
    ]}), encoding="utf-8")
    result = load_dividends(path, today=date(2026, 11, 9))
    assert result["six_month_by_symbol"][0]["symbol"] == "JEPQ"
    assert result["six_month_by_symbol"][0]["amount"] == "15"
    assert {item["symbol"] for item in result["recent"]} == {"JEPQ"}
