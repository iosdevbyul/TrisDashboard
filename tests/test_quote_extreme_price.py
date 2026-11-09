from datetime import datetime, timezone
import pytest
from backend.quotes import parse_quote, refresh_quote_freshness


NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)


@pytest.mark.parametrize("price", ["1e999999999", "1e-999999999"])
def test_provider_quote_rejects_extreme_prices(price):
    with pytest.raises(ValueError, match="Invalid quote price"):
        parse_quote({"symbol": "JEPQ", "currency": "USD", "close": price,
                     "timestamp": int(NOW.timestamp())}, "JEPQ", now=NOW)


@pytest.mark.parametrize("price", ["1e999999999", "1e-999999999"])
def test_cached_quote_extreme_price_is_outdated(price):
    result = refresh_quote_freshness({"available": True, "quotes": [{
        "symbol": "JEPQ", "currency": "USD", "price": price,
        "reported_at_utc": NOW.isoformat(), "outdated": False
    }]}, now=NOW)
    assert result["quotes"][0]["outdated"] is True


def test_normal_quote_remains_fresh():
    result = refresh_quote_freshness({"available": True, "quotes": [{
        "symbol": "JEPQ", "currency": "USD", "price": "49.99",
        "reported_at_utc": NOW.isoformat(), "outdated": True
    }]}, now=NOW)
    assert result["quotes"][0]["outdated"] is False
