from backend.valuation import quote_valuation


def test_currency_total_overflow_does_not_crash_dashboard():
    portfolio = {"available": True, "positions": [
        {"symbol": "A", "currency": "USD", "quantity": "1"},
        {"symbol": "B", "currency": "USD", "quantity": "1"},
        {"symbol": "C", "currency": "KRW", "quantity": "2"},
    ]}
    quotes = {"available": True, "quotes": [
        {"symbol": "A", "currency": "USD", "price": "6e999999", "reported_at_utc": "t"},
        {"symbol": "B", "currency": "USD", "price": "6e999999", "reported_at_utc": "t"},
        {"symbol": "C", "currency": "KRW", "price": "10", "reported_at_utc": "t"},
    ]}
    result = quote_valuation(portfolio, quotes)
    assert result["available"] is True
    assert result["matched_count"] == 2
    assert result["partial"] is True
    assert result["totals"]["KRW"] == "20"
    assert result["totals"]["USD"] == "6E+999999"
