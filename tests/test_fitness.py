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
