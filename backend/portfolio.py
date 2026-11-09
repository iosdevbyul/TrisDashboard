"""Manual, local portfolio snapshot. No brokerage login or market-price API."""
import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from backend.quality import snapshot_quality

def _reject_nonstandard_constant(value):
    raise ValueError("Non-standard JSON numeric constant: " + value)


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate portfolio JSON key")
        result[key] = value
    return result


MAX_POSITIONS = 25
CURRENCIES = {"USD", "KRW"}


def nonnegative(value, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(field + " must be numeric")
    try:
        number = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(field + " must be numeric") from error
    if (not number.is_finite() or number < 0 or
            (number != 0 and (number.adjusted() > 1000 or number.adjusted() < -1000))):
        raise ValueError(field + " must be non-negative, finite and within supported precision")
    return number


def load_portfolio(path: Path) -> dict:
    """Only user-supplied snapshot values; never infer prices, returns or dividends."""
    if path.stat().st_size > 64 * 1024:
        raise ValueError("Snapshot file too large")
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys,
                         parse_constant=_reject_nonstandard_constant)
    if not isinstance(data, dict) or not isinstance(data.get("positions"), list):
        raise ValueError("Expected positions array")
    if len(data["positions"]) > MAX_POSITIONS:
        raise ValueError("Too many positions")
    as_of = data.get("as_of")
    if not isinstance(as_of, str) or len(as_of) > 35:
        raise ValueError("as_of is required")
    try:
        parsed = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("as_of requires timezone")
    except ValueError as error:
        raise ValueError("Invalid as_of timestamp") from error
    quality = snapshot_quality(parsed)
    positions = []
    totals = {}
    seen_positions = set()
    for item in data["positions"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid position")
        symbol, currency = item.get("symbol"), item.get("currency")
        if not isinstance(symbol, str) or not 1 <= len(symbol) <= 20 or not all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.-_" for c in symbol):
            raise ValueError("Invalid ticker")
        if currency not in CURRENCIES:
            raise ValueError("Unsupported currency")
        symbol = symbol.upper()
        key = (symbol, currency)
        if key in seen_positions:
            raise ValueError("Duplicate portfolio holding")
        seen_positions.add(key)
        quantity = nonnegative(item.get("quantity"), "quantity")
        if quantity != 0 and (quantity.adjusted() > 20 or quantity.adjusted() < -20):
            raise ValueError("quantity exceeds supported precision")
        price = item.get("price")
        value = None
        price_amount = nonnegative(price, "price") if price is not None else None
        if price_amount is not None:
            if price_amount != 0 and (price_amount.adjusted() > 20 or price_amount.adjusted() < -20):
                raise ValueError("price exceeds supported precision")
            value = quantity * price_amount
            totals[currency] = totals.get(currency, Decimal("0")) + value
        positions.append({"symbol": symbol, "currency": currency,
                          "quantity": str(quantity),
                          "price": str(price_amount) if price_amount is not None else None,
                          "market_value": str(value) if value is not None else None})
    missing_prices = {}
    for position in positions:
        if position["price"] is None:
            currency = position["currency"]
            missing_prices[currency] = missing_prices.get(currency, 0) + 1
    allocations = {}
    for currency, total in totals.items():
        if total > 0 and all(p["market_value"] is not None for p in positions if p["currency"] == currency):
            allocations[currency] = [
                {"symbol": p["symbol"], "percent": str(
                    (Decimal(p["market_value"]) * 100 / total).quantize(Decimal("0.1")))}
                for p in positions if p["currency"] == currency
            ]
    concentration = {}
    for currency, total in totals.items():
        if currency in allocations and total > 0:
            values = sorted((Decimal(p["market_value"]) for p in positions
                             if p["currency"] == currency), reverse=True)
            concentration[currency] = str((sum(values[:3], Decimal("0")) * 100 / total).quantize(Decimal("0.1")))
    largest_holdings = {}
    for currency in sorted(allocations):
        options = [p for p in positions if p["currency"] == currency]
        if options:
            largest = max(options, key=lambda p: (Decimal(p["market_value"]), p["symbol"]))
            largest_holdings[currency] = {"symbol": largest["symbol"],
                                          "market_value": largest["market_value"]}
    return {"available": True, "source": "manual_snapshot", "as_of": parsed.isoformat(),
            "positions": positions, "totals": {k: str(v) for k, v in sorted(totals.items())},
            "currency_allocations": allocations,
            "unpriced_positions_by_currency": dict(sorted(missing_prices.items())),
            "top_three_concentration_percent": concentration,
            "largest_holdings": largest_holdings,
            "valuation_complete": all(p["market_value"] is not None for p in positions),
            "quality": quality,
            "stale": False}


def portfolio() -> dict:
    location = os.environ.get("TRIS_PORTFOLIO_FILE", "").strip()
    if not location:
        return {"available": False, "configured": False, "stale": False}
    try:
        data = load_portfolio(Path(location).expanduser())
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"available": False, "configured": True, "stale": True}
    data["configured"] = True
    return data
