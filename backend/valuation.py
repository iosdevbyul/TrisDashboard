"""Clearly labeled *partial* portfolio valuation using optional source-stamped quotes."""
from decimal import Decimal, InvalidOperation

def quote_valuation(portfolio: dict, quotes: dict) -> dict:
    if not portfolio.get("available"):
        return {"available": False, "reason": "portfolio-unavailable"}
    if not quotes.get("available"):
        return {"available": False, "reason": "quotes-unavailable"}
    if quotes.get("stale"):
        return {"available": False, "reason": "provider-cache-stale"}
    latest = {}
    ambiguous = set()
    for quote in quotes.get("quotes", []):
        if not isinstance(quote, dict) or quote.get("outdated") or not quote.get("price"):
            continue
        if not quote.get("symbol") or quote.get("currency") not in ("USD", "KRW"):
            continue
        key = (quote["symbol"], quote["currency"])
        if key in latest:
            ambiguous.add(key)
        else:
            latest[key] = quote
    matched = []
    totals = {}
    for item in portfolio.get("positions", []):
        if not isinstance(item, dict):
            continue
        symbol = item.get("symbol")
        currency = item.get("currency")
        key = (symbol, currency)
        quote = None if key in ambiguous else latest.get(key)
        if quote is None:
            continue
        try:
            qty = Decimal(str(item["quantity"]))
            price = Decimal(str(quote["price"]))
        except (KeyError, ValueError, InvalidOperation):
            continue
        if not qty.is_finite() or qty < 0 or not price.is_finite() or price <= 0:
            continue
        value = qty * price
        totals[currency] = totals.get(currency, Decimal("0")) + value
        matched.append({"symbol": symbol, "currency": currency, "value": str(value),
                        "quote_time_utc": quote["reported_at_utc"]})
    return {
        "available": bool(matched),
        "source": "source-stamped_quotes",
        "provider": "Twelve Data",
        "matched_count": len(matched),
        "position_count": len(portfolio.get("positions", [])),
        "partial": len(matched) < len(portfolio.get("positions", [])),
        "totals": {currency: str(value) for currency, value in sorted(totals.items())},
        "positions": matched,
        "stale": bool(quotes.get("stale")),
        "is_realtime": False,
    }
