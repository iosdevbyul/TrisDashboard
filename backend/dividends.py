"""Read-only manually recorded dividend payments; never estimates future payouts."""
import json
import os
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from backend.portfolio import nonnegative, CURRENCIES

_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _reject_nonstandard_constant(value):
    raise ValueError("Non-standard JSON numeric constant: " + value)


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate dividend JSON key")
        result[key] = value
    return result

def load_dividends(path: Path, today: date | None = None) -> dict:
    if path.stat().st_size > 65536:
        raise ValueError("Dividend file too large")
    payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys,
                         parse_constant=_reject_nonstandard_constant)
    entries = payload.get("payments") if isinstance(payload, dict) else None
    if not isinstance(entries, list) or len(entries) > 300:
        raise ValueError("Invalid dividend payments")
    reference = today or date.today()
    totals = {}
    month = reference.strftime("%Y-%m")
    months = []
    for offset in range(5, -1, -1):
        index = reference.year * 12 + (reference.month - 1) - offset
        months.append(f"{(index // 12):04d}-{(index % 12) + 1:02d}")
    history = {month_key: {} for month_key in months}
    recent = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Invalid payment")
        ticker, currency = entry.get("symbol"), entry.get("currency")
        if not isinstance(ticker, str) or not 1 <= len(ticker) <= 20 or not all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.-_" for c in ticker):
            raise ValueError("Invalid symbol")
        if currency not in CURRENCIES:
            raise ValueError("Unsupported currency")
        raw_paid = entry.get("paid_on")
        if not isinstance(raw_paid, str) or not _DATE_RE.fullmatch(raw_paid):
            raise ValueError("Invalid payment date")
        paid_on = date.fromisoformat(raw_paid)
        amount = nonnegative(entry.get("amount"), "amount")
        if paid_on > reference:
            raise ValueError("Only recorded past or current payments allowed")
        paid_month = paid_on.strftime("%Y-%m")
        if paid_month == month:
            totals[currency] = totals.get(currency, Decimal("0")) + amount
        if paid_month in history:
            monthly = history[paid_month]
            monthly[currency] = monthly.get(currency, Decimal("0")) + amount
        recent.append({"symbol": ticker, "currency": currency, "paid_on": paid_on.isoformat(), "amount": str(amount)})
    recent.sort(key=lambda item: item["paid_on"], reverse=True)
    return {"available": True, "configured": True, "source": "manual_confirmed_payments",
            "month": month, "monthly_totals": {key: str(value) for key, value in sorted(totals.items())},
            "history": [{"month": key, "totals": {currency: str(amount) for currency, amount in sorted(history[key].items())}}
                        for key in months],
            "record_count": len(entries), "recent": recent[:5], "stale": False}

def dividends() -> dict:
    file_path = os.environ.get("TRIS_DIVIDENDS_FILE", "").strip()
    if not file_path:
        return {"available": False, "configured": False, "stale": False}
    try:
        return load_dividends(Path(file_path).expanduser())
    except (OSError, ValueError, KeyError, TypeError):
        return {"available": False, "configured": True, "stale": True}
