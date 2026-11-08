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


def test_all_failed_quotes_raise_so_outage_is_not_cached():
    from backend.quotes import load_quotes
    with pytest.raises(ValueError, match="no usable prices"):
        load_quotes(["JEPQ"], "placeholder", lambda url, headers=None: {
            "status": "error", "message": "not entitled"
        })


def test_provider_outage_preserves_old_cache_as_stale(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setenv("TRIS_QUOTE_SYMBOLS", "JEPQ")
    monkeypatch.setenv("TRIS_TWELVEDATA_API_KEY", "private-test")
    monkeypatch.setattr(integrations, "get_json", lambda url, headers=None: sample())
    initial = integrations.quotes()
    assert initial["available"] and initial["stale"] is False
    # Force cache refresh without sleeping.
    key = next(k for k in integrations._cache if k.startswith("quotes:"))
    integrations._cache[key]["time"] -= 1801
    monkeypatch.setattr(integrations, "get_json", lambda url, headers=None: {"status": "error"})
    fallback = integrations.quotes()
    assert fallback["available"] and fallback["stale"] is True
    assert "private-test" not in str(fallback)


def test_twelve_data_official_quote_shape_and_distinct_bar_timestamps():
    from datetime import timedelta
    now = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)
    bar_open = int((now - timedelta(hours=2)).timestamp())
    last_minute = int((now - timedelta(minutes=1)).timestamp())
    response = {
        "symbol": "JEPQ", "name": "JPMorgan Nasdaq Equity Premium Income ETF",
        "exchange": "NASDAQ", "currency": "USD",
        "datetime": "2026-11-08 10:00:00",
        "timestamp": bar_open,
        "last_quote_at": last_minute,
        "open": "52.10000", "high": "52.90000",
        "low": "51.95000", "close": "52.42000",
        "previous_close": "52.08000",
    }
    result = parse_quote(response, "JEPQ", now)
    assert result["price"] == "52.42000"
    assert result["age_hours"] == 2.0
    assert result["reported_at_utc"] == (now - timedelta(hours=2)).isoformat()
    assert result["last_quote_at_utc"] == (now - timedelta(minutes=1)).isoformat()
    assert result["is_realtime"] is False


def test_quote_last_quote_timestamp_is_optional_and_cannot_be_spoofed():
    now = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)
    data = sample(timestamp=int((now - timedelta(hours=2)).timestamp()))
    data["last_quote_at"] = int((now + timedelta(days=1)).timestamp())
    assert parse_quote(data, "JEPQ", now)["last_quote_at_utc"] is None
    data["last_quote_at"] = "not-unix"
    assert parse_quote(data, "JEPQ", now)["last_quote_at_utc"] is None
    del data["last_quote_at"]
    assert parse_quote(data, "JEPQ", now)["last_quote_at_utc"] is None


def test_quote_vendor_error_response_is_not_a_valid_price():
    with pytest.raises(ValueError):
        parse_quote({"status": "error", "code": 429,
                     "message": "API credits exhausted"}, "JEPQ")


def test_quote_rejects_wrong_symbol_and_currency():
    with pytest.raises(ValueError):
        parse_quote(sample(symbol="OTHER"), "JEPQ")
    data = sample()
    data["currency"] = "EUR"
    with pytest.raises(ValueError):
        parse_quote(data, "JEPQ")
