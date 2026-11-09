from datetime import datetime, timezone
from backend.quotes import refresh_quote_freshness


def test_invalid_quote_timestamp_does_not_keep_cached_fresh_age():
    now = datetime(2026, 11, 9, tzinfo=timezone.utc)
    rows = [{"symbol": "JEPQ", "currency": "USD", "price": "45",
             "reported_at_utc": "bad-time", "outdated": False, "age_hours": 0}]
    result = refresh_quote_freshness({"available": True, "quotes": rows}, now=now)
    assert result["quotes"][0]["outdated"] is True
    assert "age_hours" not in result["quotes"][0]
    assert rows[0]["age_hours"] == 0
