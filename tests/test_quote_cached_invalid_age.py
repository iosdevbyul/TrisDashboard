from datetime import datetime, timezone
import pytest
from backend.quotes import refresh_quote_freshness


NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)


@pytest.mark.parametrize("override", [
    {"price": "NaN"},
    {"price": "0"},
    {"symbol": "ＪＥＰＱ"},
    {"currency": "EUR"},
    {"reported_at_utc": None},
])
def test_bad_cached_quote_clears_misleading_age(override):
    original = {"symbol": "JEPQ", "currency": "USD", "price": "50",
                "reported_at_utc": NOW.isoformat(), "age_hours": 0, "outdated": False}
    value = refresh_quote_freshness({"available": True, "quotes": [{**original, **override}]}, now=NOW)
    assert value["quotes"][0]["outdated"] is True
    assert "age_hours" not in value["quotes"][0]


def test_valid_quote_retains_computed_age():
    value = refresh_quote_freshness({"available": True, "quotes": [{
        "symbol": "JEPQ", "currency": "USD", "price": "50",
        "reported_at_utc": NOW.isoformat(), "age_hours": 999, "outdated": True
    }]}, now=NOW)
    assert value["quotes"][0]["outdated"] is False
    assert value["quotes"][0]["age_hours"] == 0.0
