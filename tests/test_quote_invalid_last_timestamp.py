from datetime import datetime, timezone
import pytest
from backend.quotes import refresh_quote_freshness

NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)


@pytest.mark.parametrize("override", [
    {"reported_at_utc": "bad"},
    {"symbol": "ＪＥＰＱ"},
    {"price": "0"},
    {"reported_at_utc": None},
])
def test_invalid_cached_quotes_discard_untrusted_last_observation(override):
    row = {"symbol": "JEPQ", "currency": "USD", "price": "55",
           "reported_at_utc": NOW.isoformat(), "age_hours": 0,
           "last_quote_at_utc": NOW.isoformat()}
    result = refresh_quote_freshness({"available": True, "quotes": [{**row, **override}]}, now=NOW)
    assert result["quotes"][0]["outdated"] is True
    assert "last_quote_at_utc" not in result["quotes"][0]


def test_valid_cached_quotes_preserve_last_observation():
    row = {"symbol": "JEPQ", "currency": "USD", "price": "55",
           "reported_at_utc": NOW.isoformat(), "last_quote_at_utc": NOW.isoformat()}
    result = refresh_quote_freshness({"available": True, "quotes": [row]}, now=NOW)
    assert result["quotes"][0]["last_quote_at_utc"] == NOW.isoformat()
