from backend.valuation import quote_valuation

def test_valuation_matches_symbols_and_currencies_without_guesswork():
    portfolio = {"available": True, "positions": [
        {"symbol": "JEPQ", "currency": "USD", "quantity": "10", "price": "30"},
        {"symbol": "QQQI", "currency": "USD", "quantity": "2"},
        {"symbol": "KRTEST", "currency": "KRW", "quantity": "7"},
    ]}
    quotes = {"available": True, "quotes": [
        {"symbol": "JEPQ", "currency": "USD", "price": "50", "reported_at_utc": "2026-11-08T00:00:00+00:00"},
        {"symbol": "QQQI", "currency": "KRW", "price": "100000", "reported_at_utc": "2026-11-08T00:00:00+00:00"},
    ]}
    result = quote_valuation(portfolio, quotes)
    assert result["totals"] == {"USD": "500"}
    assert result["matched_count"] == 1
    assert result["partial"] is True
    assert result["is_realtime"] is False
    assert portfolio["positions"][0]["price"] == "30"


def test_old_quote_does_not_value_position():
    portfolio = {"available": True, "positions": [{"symbol": "JEPQ", "currency": "USD", "quantity": "2"}]}
    quotes = {"available": True, "quotes": [{"symbol": "JEPQ", "currency": "USD",
             "price": "50", "reported_at_utc": "old", "outdated": True}]}
    assert quote_valuation(portfolio, quotes)["available"] is False


def test_currency_separation_and_decimal_exactness():
    portfolio = {"available": True, "positions": [
        {"symbol": "A", "currency": "USD", "quantity": "0.1"},
        {"symbol": "B", "currency": "KRW", "quantity": "2"},
    ]}
    quotes = {"available": True, "quotes": [
        {"symbol": "A", "currency": "USD", "price": "0.2", "reported_at_utc": "t"},
        {"symbol": "B", "currency": "KRW", "price": "100", "reported_at_utc": "t"},
    ]}
    result = quote_valuation(portfolio, quotes)
    assert result["totals"] == {"KRW": "200", "USD": "0.02"}
    assert result["partial"] is False


def test_absent_market_provider_keeps_manual_snapshot_separate():
    portfolio = {"available": True, "positions": [{"symbol": "A", "currency": "USD", "quantity": "2"}]}
    assert quote_valuation(portfolio, {"available": False}) == {
        "available": False, "reason": "quotes-unavailable"}


def test_stale_provider_cache_cannot_produce_actionable_holdings_value():
    portfolio = {"available": True, "positions": [
        {"symbol": "JEPQ", "currency": "USD", "quantity": "10"}]}
    quotes = {"available": True, "stale": True, "quotes": [{
        "symbol": "JEPQ", "currency": "USD", "price": "60",
        "reported_at_utc": "2026-11-08T00:00:00+00:00", "outdated": False}]}
    assert quote_valuation(portfolio, quotes) == {
        "available": False, "reason": "provider-cache-stale"}
