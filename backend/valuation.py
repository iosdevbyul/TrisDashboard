"""Clearly labeled *partial* portfolio valuation using optional source-stamped quotes."""
from decimal import Decimal, InvalidOperation, Overflow

def quote_valuation(portfolio: dict, quotes: dict) -> dict:
    if not isinstance(portfolio, dict) or not portfolio.get("available"):
        return {"available": False, "reason": "portfolio-unavailable"}
    if not isinstance(portfolio.get("positions"), list):
        return {"available": False, "reason": "portfolio-unavailable"}
    if not isinstance(quotes, dict) or not isinstance(quotes.get("quotes"), list):
        return {"available": False, "reason": "quotes-unavailable"}
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
        if not isinstance(quote.get("symbol"), str) or not quote["symbol"] or quote.get("currency") not in ("USD", "KRW"):
            continue
        if not isinstance(quote.get("reported_at_utc"), str) or not quote["reported_at_utc"]:
            continue
        key = (quote["symbol"], quote["currency"])
        if key in latest:
            ambiguous.add(key)
        else:
            latest[key] = quote
    matched = []
    totals = {}
    seen_positions = set()
    duplicated_positions = set()
    for item in portfolio["positions"]:
        if not isinstance(item, dict):
            continue
        key = (item.get("symbol"), item.get("currency"))
        if not all(isinstance(part, str) for part in key):
            continue
        if key in seen_positions:
            duplicated_positions.add(key)
        seen_positions.add(key)
    for item in portfolio["positions"]:
        if not isinstance(item, dict):
            continue
        symbol = item.get("symbol")
        currency = item.get("currency")
        if not isinstance(symbol, str) or not isinstance(currency, str):
            continue
        key = (symbol, currency)
        quote = None if key in ambiguous or key in duplicated_positions else latest.get(key)
        if quote is None:
            continue
        if isinstance(item.get("quantity"), bool) or isinstance(quote.get("price"), bool):
            continue
        try:
            qty = Decimal(str(item["quantity"]))
            price = Decimal(str(quote["price"]))
        except (KeyError, ValueError, InvalidOperation):
            continue
        if not qty.is_finite() or qty < 0 or not price.is_finite() or price <= 0:
            continue
        try:
            value = qty * price
        except (InvalidOperation, Overflow, OverflowError):
            continue
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
