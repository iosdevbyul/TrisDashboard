"""Optional Twelve Data quote readings: source timestamp is NOT a real-time promise."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode


def quote_symbols(raw: str) -> list[str]:
    names = []
    for item in raw.split(","):
        symbol = item.strip().upper()
        if not symbol or len(symbol) > 20 or any(not (c.isalnum() or c in ".-_") for c in symbol):
            raise ValueError("Invalid quote symbol")
        if symbol not in names:
            names.append(symbol)
        if len(names) > 2:
            raise ValueError("At most two symbols per refresh")
    return names


def parse_quote(data: dict, expected_symbol: str, now: datetime | None = None) -> dict:
    if not isinstance(data, dict) or data.get("status") == "error":
        raise ValueError("Market data unavailable")
    symbol = data.get("symbol")
    currency = data.get("currency")
    if not isinstance(symbol, str) or symbol.upper() != expected_symbol:
        raise ValueError("Unexpected symbol")
    if currency not in ("USD", "KRW"):
        raise ValueError("Unexpected quote currency")
    try:
        value = Decimal(str(data["close"]))
        timestamp = data["timestamp"]
        if type(timestamp) is not int:
            raise ValueError("Timestamp must be numeric Unix seconds")
        reported_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (ValueError, TypeError, KeyError, OverflowError, OSError, InvalidOperation) as error:
        raise ValueError("Malformed quote") from error
    current = now or datetime.now(timezone.utc)
    age_seconds = (current - reported_at).total_seconds()
    if not value.is_finite() or value <= 0 or age_seconds < -600 or age_seconds > 365 * 86400:
        raise ValueError("Invalid quote price or timestamp")
    return {
        "symbol": symbol.upper(),
        "currency": currency,
        "price": str(value),
        "reported_at_utc": reported_at.isoformat(),
        "age_hours": round(max(age_seconds, 0) / 3600, 1),
        "outdated": age_seconds > 72 * 3600,
        "provider": "Twelve Data",
        "is_realtime": False,
    }


def load_quotes(symbols: list[str], token: str, fetcher) -> dict:
    readings = []
    for symbol in symbols:
        try:
            # API key is never appended to an URL or exposed to browser clients.
            url = "https://api.twelvedata.com/quote?" + urlencode({"symbol": symbol})
            payload = fetcher(url, headers={"Authorization": "apikey " + token})
            readings.append(parse_quote(payload, symbol))
        except (OSError, ValueError, TypeError, KeyError):
            readings.append({"symbol": symbol, "available": False})
    return {
        "available": any(item.get("price") for item in readings),
        "configured": True,
        "provider": "Twelve Data",
        "quotes": readings,
        "partial": any(item.get("available") is False for item in readings),
    }
