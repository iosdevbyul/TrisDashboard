from backend.valuation import quote_valuation


def test_extreme_decimal_value_does_not_crash_or_hide_valid_holding():
    portfolio = {"available": True, "positions": [
        {"symbol": "EXTREME", "currency": "USD", "quantity": "1e999999999"},
        {"symbol": "NORMAL", "currency": "USD", "quantity": "2"},
    ]}
    quotes = {"available": True, "quotes": [
        {"symbol": "EXTREME", "currency": "USD", "price": "1e999999999", "reported_at_utc": "t"},
        {"symbol": "NORMAL", "currency": "USD", "price": "50", "reported_at_utc": "t"},
    ]}
    result = quote_valuation(portfolio, quotes)
    assert result["totals"] == {"USD": "100"}
    assert result["matched_count"] == 1
    assert result["partial"] is True
