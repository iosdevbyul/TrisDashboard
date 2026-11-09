from datetime import datetime, timezone
from backend.quotes import refresh_quote_freshness


def test_quote_cache_marks_invalid_symbol_or_currency_outdated():
    now = datetime(2026, 11, 9, tzinfo=timezone.utc)
    row = {"symbol": "JEPQ", "currency": "USD", "price": "50", "reported_at_utc": now.isoformat(), "outdated": False}
    payload = {"available": True, "quotes": [
        {**row, "symbol": "jepq"},
        {**row, "currency": "EUR"},
        {**row, "symbol": "ＪＥＰＱ"},
        row,
    ]}
    result = refresh_quote_freshness(payload, now=now)
    assert [item["outdated"] for item in result["quotes"]] == [True, True, True, False]
    assert payload["quotes"][0]["outdated"] is False
