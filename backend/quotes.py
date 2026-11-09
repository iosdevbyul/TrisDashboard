"""Optional Twelve Data quote readings: source timestamp is NOT a real-time promise."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode


def quote_symbols(raw: str) -> list[str]:
    if not isinstance(raw, str):
        raise ValueError("Invalid quote symbols")
    names = []
    for item in raw.split(","):
        symbol = item.strip().upper()
        if not symbol or len(symbol) > 20 or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_" for c in symbol):
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
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("Quote reference must have timezone")
    age_seconds = (current - reported_at).total_seconds()
    # Twelve Data reports bar-open time in timestamp, while last_quote_at
    # is the optional last-minute candle time. These are not interchangeable.
    last_quote_at = None
    if "last_quote_at" in data:
        candidate = data["last_quote_at"]
        if type(candidate) is int:
            try:
                observed = datetime.fromtimestamp(candidate, tz=timezone.utc)
                if reported_at <= observed <= current + timedelta(minutes=10):
                    last_quote_at = observed.isoformat()
            except (ValueError, OverflowError, OSError):
                pass
    if (not value.is_finite() or value <= 0 or value.adjusted() > 1000
            or value.adjusted() < -1000 or age_seconds < -600 or age_seconds > 365 * 86400):
        raise ValueError("Invalid quote price or timestamp")
    return {
        "symbol": symbol.upper(),
        "currency": currency,
        "price": str(value),
        "reported_at_utc": reported_at.isoformat(),
        "last_quote_at_utc": last_quote_at,
        "age_hours": round(max(age_seconds, 0) / 3600, 1),
        "outdated": age_seconds > 72 * 3600,
        "provider": "Twelve Data",
        "is_realtime": False,
    }


def refresh_quote_freshness(payload: dict, now: datetime | None = None) -> dict:
    """Re-evaluate timestamps at display time; cached quotes cannot remain 'fresh' forever."""
    if not isinstance(payload, dict):
        raise ValueError("Invalid quote cache")
    if not payload.get("available"):
        return dict(payload)
    current = datetime.now(timezone.utc) if now is None else now
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("Quote reference must have timezone")
    quotes = payload.get("quotes")
    if not isinstance(quotes, list):
        raise ValueError("Invalid quote cache rows")
    result = dict(payload)
    readings = []
    for quote in quotes:
        if not isinstance(quote, dict):
            continue
        item = dict(quote)
        try:
            value = Decimal(str(item.get("price")))
            valid_price = (not isinstance(item.get("price"), bool) and value.is_finite()
                           and value > 0 and -1000 <= value.adjusted() <= 1000)
        except (ValueError, TypeError, InvalidOperation):
            valid_price = False
        valid_identity = (isinstance(item.get("symbol"), str) and
                          1 <= len(item["symbol"]) <= 20 and
                          all(char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_" for char in item["symbol"]) and
                          item.get("currency") in ("USD", "KRW"))
        if not valid_price or not valid_identity or not item.get("reported_at_utc"):
            item["outdated"] = True
        if valid_price and valid_identity and item.get("reported_at_utc"):
            try:
                timestamp = datetime.fromisoformat(item["reported_at_utc"])
                if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                    raise ValueError("Missing quote timezone")
                seconds = (current - timestamp).total_seconds()
                item["outdated"] = seconds > 72 * 3600 or seconds < -600
                item["age_hours"] = round(max(0, seconds) / 3600, 1)
            except (ValueError, TypeError):
                item["outdated"] = True
        readings.append(item)
    result["quotes"] = readings
    return result


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
    if not any(item.get("price") for item in readings):
        # Do not cache a total upstream outage for thirty minutes.
        raise ValueError("Market quote provider returned no usable prices")
    return {
        "available": True,
        "configured": True,
        "provider": "Twelve Data",
        "quotes": readings,
        "partial": any(item.get("available") is False for item in readings),
    }
