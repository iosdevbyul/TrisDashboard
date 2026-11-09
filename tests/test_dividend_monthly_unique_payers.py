import json
from datetime import date
from backend.dividends import load_dividends


def test_monthly_unique_payers_deduplicates_symbol(tmp_path):
    path = tmp_path / "dividends.json"
    path.write_text(json.dumps({"payments": [
        {"symbol":"JEPQ","currency":"USD","paid_on":"2026-11-03","amount":"4"},
        {"symbol":"jepq","currency":"USD","paid_on":"2026-11-04","amount":"5"},
        {"symbol":"SCHD","currency":"USD","paid_on":"2026-11-06","amount":"3"},
        {"symbol":"SCHD","currency":"USD","paid_on":"2026-10-06","amount":"2"},
    ]}), encoding="utf-8")
    result = load_dividends(path, today=date(2026,11,9))
    assert result["monthly_unique_paying_symbols"] == {"USD": 2}
    assert result["monthly_payment_counts"] == {"USD": 3}
