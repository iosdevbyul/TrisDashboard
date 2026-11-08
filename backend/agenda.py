"""Local calendar list from explicitly supplied private JSON, no cloud calendar access."""
import json
import os
import re
from datetime import date, timedelta
from pathlib import Path

_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_TIME_PATTERN = re.compile(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]")


def _reject_nonstandard_constant(value):
    raise ValueError("Non-standard JSON numeric constant: " + value)


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate agenda JSON key")
        result[key] = value
    return result


def load_agenda(path: Path, today: date | None = None) -> dict:
    if path.stat().st_size > 65536:
        raise ValueError("Agenda file too large")
    payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys,
                         parse_constant=_reject_nonstandard_constant)
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list) or len(events) > 300:
        raise ValueError("Invalid agenda")
    reference = today or date.today()
    end = reference + timedelta(days=14)
    upcoming = []
    for item in events:
        if not isinstance(item, dict):
            raise ValueError("Invalid event")
        raw_day = item.get("date")
        if not isinstance(raw_day, str) or not _DATE_PATTERN.fullmatch(raw_day):
            raise ValueError("Invalid event date")
        day = date.fromisoformat(raw_day)
        title = item.get("title")
        if (not isinstance(title, str) or not title.strip() or len(title) > 120
                or any(ord(char) < 32 or ord(char) == 127 for char in title)):
            raise ValueError("Invalid event title")
        when = item.get("time", "")
        if not isinstance(when, str) or (when and not _TIME_PATTERN.fullmatch(when)):
            raise ValueError("Invalid time")
        if reference <= day <= end:
            upcoming.append({"date": day.isoformat(), "time": when, "title": title.strip()})
    upcoming.sort(key=lambda event: (event["date"], event["time"]))
    return {"available": True, "configured": True, "source": "manual_local_calendar",
            "window_start": reference.isoformat(), "window_end": end.isoformat(),
            "upcoming_count": len(upcoming), "events": upcoming[:8], "stale": False}


def agenda() -> dict:
    location = os.environ.get("TRIS_AGENDA_FILE", "").strip()
    if not location:
        return {"available": False, "configured": False, "stale": False}
    try:
        return load_agenda(Path(location).expanduser())
    except (OSError, ValueError, TypeError, KeyError):
        return {"available": False, "configured": True, "stale": True}
