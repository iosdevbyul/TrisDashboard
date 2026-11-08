import json
from datetime import date

import pytest

from backend.fitness import fitness, load_fitness


def snapshot(tmp_path, workouts):
    path = tmp_path / "workouts.json"
    path.write_text(json.dumps({"workouts": workouts}))
    return path


def test_recent_seven_day_summary_and_exclude_old(tmp_path):
    path = snapshot(tmp_path, [
        {"date": "2026-11-08", "type": "Running", "duration_minutes": 42, "distance_km": 7.2},
        {"date": "2026-11-05", "type": "Strength", "duration_minutes": 60},
        {"date": "2026-10-31", "type": "Cycling", "duration_minutes": 20},
    ])
    data = load_fitness(path, today=date(2026, 11, 8))
    assert data["summary"] == {"sessions": 2, "duration_minutes": 102, "distance_km": 7.2}
    assert [item["type"] for item in data["recent"]] == ["Running", "Strength"]


@pytest.mark.parametrize("invalid", [-1, True, "ten", float("nan"), float("inf")])
def test_bad_duration_rejected(tmp_path, invalid):
    path = snapshot(tmp_path, [{"date": "2026-11-08", "type": "Running", "duration_minutes": invalid}])
    with pytest.raises(ValueError):
        load_fitness(path, today=date(2026, 11, 8))


def test_missing_or_invalid_file_is_safe(tmp_path, monkeypatch):
    monkeypatch.delenv("TRIS_FITNESS_FILE", raising=False)
    assert fitness()["configured"] is False
    path = tmp_path / "workouts.json"
    path.write_text("{invalid")
    monkeypatch.setenv("TRIS_FITNESS_FILE", str(path))
    assert fitness() == {"available": False, "configured": True, "stale": True}


def test_duplicate_stable_ids_are_rejected_before_summary(tmp_path):
    workout = {"session_id": "wak-session-001", "date": "2026-11-08",
               "type": "Running", "duration_minutes": 30, "distance_km": 5}
    path = snapshot(tmp_path, [workout, dict(workout, duration_minutes=40)])
    with pytest.raises(ValueError, match="Duplicate workout session ID"):
        load_fitness(path, today=date(2026, 11, 8))


def test_legacy_workouts_and_v2_identity_coverage(tmp_path):
    path = snapshot(tmp_path, [
        {"date": "2026-11-08", "type": "Strength", "duration_minutes": 45},
        {"session_id": "stable-101", "date": "2026-11-08",
         "type": "Running", "duration_minutes": 30, "distance_km": 4.5},
    ])
    data = load_fitness(path, today=date(2026, 11, 8))
    assert data["summary"]["sessions"] == 2
    assert data["total_history_count"] == 2
    assert data["stable_id_count"] == 1


def test_duplicate_id_outside_seven_day_window_is_still_invalid(tmp_path):
    path = snapshot(tmp_path, [
        {"session_id": "same", "date": "2025-10-08",
         "type": "Running", "duration_minutes": 20},
        {"session_id": "same", "date": "2026-11-08",
         "type": "Running", "duration_minutes": 30},
    ])
    with pytest.raises(ValueError, match="Duplicate"):
        load_fitness(path, today=date(2026, 11, 8))


def test_daily_workout_breakdown_includes_empty_days(tmp_path):
    path = snapshot(tmp_path, [
        {"date": "2026-11-08", "type": "Running", "duration_minutes": 20, "distance_km": 3.1},
        {"date": "2026-11-08", "type": "Strength", "duration_minutes": 40},
        {"date": "2026-11-05", "type": "Walking", "duration_minutes": 30, "distance_km": 2.2},
        {"date": "2026-10-20", "type": "Cycling", "duration_minutes": 60},
    ])
    days = load_fitness(path, today=date(2026, 11, 8))["daily"]
    assert len(days) == 7
    assert days[0] == {"date": "2026-11-02", "sessions": 0,
                       "duration_minutes": 0, "distance_km": 0.0}
    assert days[-1] == {"date": "2026-11-08", "sessions": 2,
                        "duration_minutes": 60, "distance_km": 3.1}
    assert days[3]["date"] == "2026-11-05"
    assert days[3]["distance_km"] == 2.2
    assert sum(day["sessions"] for day in days) == 3


def test_workout_file_freshness_reports_source_mtime(tmp_path):
    import os
    from datetime import datetime, timedelta, timezone
    path = snapshot(tmp_path, [{"date": "2026-11-08", "type": "Running",
                                "duration_minutes": 30}])
    modified = datetime.now(timezone.utc) - timedelta(days=8)
    os.utime(path, (modified.timestamp(), modified.timestamp()))
    data = load_fitness(path, today=date(2026, 11, 8))
    assert data["file_older_than_week"] is True
    assert data["file_age_hours"] >= 190
    assert datetime.fromisoformat(data["file_updated_utc"]).tzinfo is not None
    assert data["stale"] is False


def test_fitness_file_freshness_does_not_infer_last_workout(tmp_path):
    path = snapshot(tmp_path, [{"date": "2023-11-08", "type": "Running",
                                "duration_minutes": 30}])
    data = load_fitness(path, today=date(2026, 11, 8))
    assert data["file_older_than_week"] is False
    assert data["summary"]["sessions"] == 0


@pytest.mark.parametrize("bad_date", ["20261108", "2026-11-8", "2026-02-30", "２０２６-11-08", 20261108])
def test_reject_invalid_workout_date(tmp_path, bad_date):
    path = snapshot(tmp_path, [{"date": bad_date, "type": "Running", "duration_minutes": 30}])
    with pytest.raises(ValueError):
        load_fitness(path, today=date(2026, 11, 8))


def test_reject_ambiguous_workout_json_keys(tmp_path):
    path = tmp_path / "fitness.json"
    path.write_text('{"workouts":[{"date":"2026-11-08","type":"Running","type":"Cycling","duration_minutes":30}]}')
    with pytest.raises(ValueError, match="Duplicate"):
        load_fitness(path, today=date(2026, 11, 8))


def test_reject_non_ascii_session_id(tmp_path):
    path = snapshot(tmp_path, [{"date":"2026-11-08", "type":"Running",
                                "duration_minutes":30, "session_id":"ｓｅｓｓｉｏｎ"}])
    with pytest.raises(ValueError):
        load_fitness(path, today=date(2026, 11, 8))


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_reject_nonstandard_json_numeric_constant_anywhere(tmp_path, constant):
    path = tmp_path / "invalid-fitness.json"
    path.write_text('{"metadata":' + constant + ',"workouts":[]}')
    with pytest.raises(ValueError, match="Non-standard JSON"):
        load_fitness(path, today=date(2026, 11, 8))


def test_future_workout_rejected_before_weekly_summary(tmp_path):
    path = snapshot(tmp_path, [{"date": "2026-11-09", "type": "Running", "duration_minutes": 30}])
    with pytest.raises(ValueError, match="Future workout"):
        load_fitness(path, today=date(2026, 11, 8))


def test_workout_active_days_count_unique_dates_not_sessions(tmp_path):
    path = snapshot(tmp_path, [
        {"date": "2026-11-08", "type": "Running", "duration_minutes": 20},
        {"date": "2026-11-08", "type": "Strength", "duration_minutes": 40},
        {"date": "2026-11-06", "type": "Walking", "duration_minutes": 10},
        {"date": "2026-10-31", "type": "Cycling", "duration_minutes": 30},
    ])
    result = load_fitness(path, today=date(2026, 11, 8))
    assert result["summary"]["sessions"] == 3
    assert result["active_days"] == 2
    assert len(result["daily"]) == 7


def test_weekly_activity_breakdown_separates_categories_and_excludes_old(tmp_path):
    source = snapshot(tmp_path, [
        {"date": "2026-11-08", "type": "Running", "duration_minutes": 20, "distance_km": 3},
        {"date": "2026-11-07", "type": "Strength", "duration_minutes": 40},
        {"date": "2026-11-06", "type": "Running", "duration_minutes": 25, "distance_km": 4},
        {"date": "2026-10-01", "type": "Cycling", "duration_minutes": 120},
    ])
    result = load_fitness(source, today=date(2026, 11, 8))
    assert result["activity_breakdown"] == [
        {"type": "Running", "sessions": 2, "duration_minutes": 45, "distance_km": 7},
        {"type": "Strength", "sessions": 1, "duration_minutes": 40, "distance_km": 0},
    ]
    assert result["summary"]["sessions"] == 3


def test_weekly_streak_counts_consecutive_active_days(tmp_path):
    workouts = [
        {"date": day, "type": "Running", "duration_minutes": 20}
        for day in ["2026-11-02", "2026-11-03", "2026-11-05", "2026-11-06", "2026-11-07"]]
    result = load_fitness(snapshot(tmp_path, workouts), today=date(2026, 11, 8))
    assert result["longest_streak_days"] == 3
    assert result["ongoing_streak_days"] == 0
    workouts.append({"date": "2026-11-08", "type": "Running", "duration_minutes": 20})
    result = load_fitness(snapshot(tmp_path, workouts), today=date(2026, 11, 8))
    assert result["longest_streak_days"] == 4
    assert result["ongoing_streak_days"] == 4


def test_average_workout_minutes_counts_only_active_days(tmp_path):
    source = snapshot(tmp_path, [
        {"date":"2026-11-09","type":"Running","duration_minutes":30},
        {"date":"2026-11-09","type":"Strength","duration_minutes":60},
        {"date":"2026-11-07","type":"Walking","duration_minutes":30},
    ])
    result = load_fitness(source, today=date(2026, 11, 9))
    assert result["active_days"] == 2
    assert result["average_active_day_minutes"] == 60.0
    empty = load_fitness(snapshot(tmp_path, []), today=date(2026, 11, 9))
    assert empty["average_active_day_minutes"] == 0.0
