"""Local calendar list from explicitly supplied private JSON, no cloud calendar access."""
import json
import os
from datetime import date, timedelta
from pathlib import Path


def load_agenda(path: Path, today: date | None = None) -> dict:
    if path.stat().st_size > 65536:
        raise ValueError("Agenda file too large")
    payload = json.loads(path.read_text(encoding="utf-8"))
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list) or len(events) > 300:
        raise ValueError("Invalid agenda")
    reference = today or date.today()
    end = reference + timedelta(days=14)
    upcoming = []
    for item in events:
        if not isinstance(item, dict):
            raise ValueError("Invalid event")
        day = date.fromisoformat(item["date"])
        title = item.get("title")
        if not isinstance(title, str) or not title.strip() or len(title) > 120:
            raise ValueError("Invalid event title")
        if not isinstance(item.get("time", ""), str):
            raise ValueError("Invalid time")
        when = item.get("time", "")
        if when and (len(when) != 5 or when[2] != ":" or
                     not (when[:2].isdigit() and when[3:].isdigit() and
                          0 <= int(when[:2]) <= 23 and 0 <= int(when[3:]) <= 59)):
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
