"""Local calendar list from explicitly supplied private JSON, no cloud calendar access."""
import json
import os
import re
from datetime import date, datetime, timedelta
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
    if today is not None and (not isinstance(today, date) or isinstance(today, datetime)):
        raise ValueError("Invalid agenda reference date")
    reference = date.today() if today is None else today
    remaining_days = (date.max - reference).days
    end = reference + timedelta(days=min(14, remaining_days))
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
                or any(ord(char) < 32 or ord(char) == 127 or
                       0x202A <= ord(char) <= 0x202E or
                       0x2066 <= ord(char) <= 0x2069 or
                       ord(char) in (0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF)
                       for char in title)):
            raise ValueError("Invalid event title")
        when = item.get("time", "")
        if not isinstance(when, str) or (when and not _TIME_PATTERN.fullmatch(when)):
            raise ValueError("Invalid time")
        if reference <= day <= end:
            upcoming.append({"date": day.isoformat(), "time": when, "title": title.strip()})
    upcoming.sort(key=lambda event: (event["date"], event["time"]))
    counts_by_day = {}
    for event in upcoming:
        counts_by_day[event["date"]] = counts_by_day.get(event["date"], 0) + 1
    busiest_day = None
    if counts_by_day:
        busiest_date = min(counts_by_day, key=lambda day: (-counts_by_day[day], day))
        busiest_day = {"date": busiest_date, "events": counts_by_day[busiest_date]}
    timed_slots = {}
    for event in upcoming:
        if event["time"]:
            slot = (event["date"], event["time"])
            timed_slots[slot] = timed_slots.get(slot, 0) + 1
    conflicting_slots = sum(1 for count in timed_slots.values() if count > 1)
    conflicting_events = sum(count for count in timed_slots.values() if count > 1)
    seven_day_end = (reference + timedelta(days=min(6, remaining_days))).isoformat()
    next_seven_days_count = sum(1 for event in upcoming if event["date"] <= seven_day_end)
    busy_dates = {event["date"] for event in upcoming if event["date"] <= seven_day_end}
    next_seven_busy_days = len(busy_dates)
    first_free_day = next((candidate.isoformat()
                           for index in range(min(7, remaining_days + 1))
                           for candidate in [reference + timedelta(days=index)]
                           if candidate.isoformat() not in busy_dates), None)
    today_event_count = sum(1 for event in upcoming if event["date"] == reference.isoformat())
    tomorrow = (reference + timedelta(days=1)).isoformat() if remaining_days else None
    tomorrow_event_count = sum(1 for event in upcoming if event["date"] == tomorrow)
    next_event_days = ((date.fromisoformat(upcoming[0]["date"]) - reference).days
                       if upcoming else None)
    next_event = dict(upcoming[0]) if upcoming else None
    return {"available": True, "configured": True, "source": "manual_local_calendar",
            "window_start": reference.isoformat(), "window_end": end.isoformat(),
            "upcoming_count": len(upcoming), "today_event_count": today_event_count,
            "busiest_upcoming_day": busiest_day,
            "conflicting_time_slots": conflicting_slots,
            "conflicting_event_count": conflicting_events,
            "tomorrow_event_count": tomorrow_event_count,
            "next_seven_days_count": next_seven_days_count,
            "next_seven_busy_days": next_seven_busy_days,
            "first_free_day_in_next_seven": first_free_day,
            "next_event_in_days": next_event_days,
            "next_event": next_event,
            "events": upcoming[:30], "events_truncated": len(upcoming) > 30,
            "stale": False}


def agenda() -> dict:
    location = os.environ.get("TRIS_AGENDA_FILE", "").strip()
    if not location:
        return {"available": False, "configured": False, "stale": False}
    try:
        return load_agenda(Path(location).expanduser())
    except (OSError, ValueError, TypeError, KeyError):
        return {"available": False, "configured": True, "stale": True}
