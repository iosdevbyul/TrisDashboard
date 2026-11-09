import json
from datetime import date
from backend.agenda import load_agenda


def read(tmp_path, days, today=date(2026, 11, 9)):
    file = tmp_path / "agenda.json"
    file.write_text(json.dumps({"events": [
        {"date": day, "title": "Scheduled"} for day in days
    ]}), encoding="utf-8")
    return load_agenda(file, today=today)


def test_first_free_day_skips_busy_dates_and_ignores_multiple_events(tmp_path):
    data = read(tmp_path, ["2026-11-09", "2026-11-09", "2026-11-10"])
    assert data["first_free_day_in_next_seven"] == "2026-11-11"
    assert data["next_seven_busy_days"] == 2


def test_all_seven_days_booked_returns_no_free_day(tmp_path):
    days = ["2026-11-%02d" % day for day in range(9, 16)]
    assert read(tmp_path, days)["first_free_day_in_next_seven"] is None


def test_empty_agenda_has_free_today(tmp_path):
    assert read(tmp_path, [])["first_free_day_in_next_seven"] == "2026-11-09"


def test_end_of_calendar_never_overflows(tmp_path):
    data = read(tmp_path, ["9999-12-31"], date(9999, 12, 31))
    assert data["first_free_day_in_next_seven"] is None
