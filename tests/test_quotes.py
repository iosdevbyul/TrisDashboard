from datetime import datetime, timezone, timedelta
import pytest
from backend.quotes import quote_symbols, parse_quote, load_quotes
from backend import integrations


def sample(symbol="JEPQ", timestamp=None, close="52.4"):
    if timestamp is None:
        timestamp = int(datetime.now(timezone.utc).timestamp()) - 300
    return {"symbol": symbol, "currency": "USD", "close": close, "timestamp": timestamp}


def test_quote_timestamp_is_explicit_and_not_claimed_realtime():
    now = datetime(2026, 11, 8, tzinfo=timezone.utc)
    quote = parse_quote(sample(timestamp=int((now - timedelta(hours=2)).timestamp())), "JEPQ", now)
    assert quote["price"] == "52.4"
    assert quote["age_hours"] == 2.0
    assert quote["is_realtime"] is False


def test_old_quote_marked_outdated():
    now = datetime(2026, 11, 8, tzinfo=timezone.utc)
    quote = parse_quote(sample(timestamp=int((now - timedelta(days=5)).timestamp())), "JEPQ", now)
    assert quote["outdated"] is True


@pytest.mark.parametrize("price", ["NaN", "Infinity", "-1", "0"])
def test_bad_price_rejected(price):
    with pytest.raises(ValueError):
        parse_quote(sample(close=price), "JEPQ")


def test_symbols_bounded_and_deduplicated():
    assert quote_symbols("jepq, JEPQ, qqqi") == ["JEPQ", "QQQI"]
    with pytest.raises(ValueError):
        quote_symbols("JEPQ,QQQI,SCHD")


def test_provider_auth_in_header_no_query_token():
    called = []
    def fetch(url, headers=None):
        called.append((url, headers))
        return sample(symbol="JEPQ")
    result = load_quotes(["JEPQ"], "sensitive-api-key", fetch)
    assert result["available"]
    assert called[0][1] == {"Authorization": "apikey sensitive-api-key"}
    assert "sensitive-api-key" not in called[0][0]
    assert "sensitive-api-key" not in str(result)


def test_quotes_unconfigured_without_key(monkeypatch):
    monkeypatch.setenv("TRIS_QUOTE_SYMBOLS", "JEPQ")
    monkeypatch.delenv("TRIS_TWELVEDATA_API_KEY", raising=False)
    assert integrations.quotes()["configured"] is False


def test_cached_quote_becomes_outdated_without_provider_refresh():
    from backend.quotes import refresh_quote_freshness
    now = datetime(2026, 11, 8, tzinfo=timezone.utc)
    quote = parse_quote(sample(timestamp=int((now - timedelta(hours=71)).timestamp())), "JEPQ", now)
    original = {"available": True, "quotes": [quote]}
    updated = refresh_quote_freshness(original, now + timedelta(hours=2))
    assert updated["quotes"][0]["outdated"] is True
    assert original["quotes"][0]["outdated"] is False
    assert updated["quotes"][0]["age_hours"] == 73.0


def test_cached_quote_invalid_timestamp_is_not_trusted():
    from backend.quotes import refresh_quote_freshness
    original = {"available": True, "quotes": [{
        "symbol": "JEPQ", "price": "52", "reported_at_utc": "not-a-time", "outdated": False}]}
    assert refresh_quote_freshness(original)["quotes"][0]["outdated"] is True
