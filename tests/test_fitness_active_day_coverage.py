import json
from datetime import date
from backend.fitness import load_fitness


def write(tmp_path, workouts):
    path = tmp_path / "fitness.json"
    path.write_text(json.dumps({"workouts": workouts}), encoding="utf-8")
    return path


def test_active_day_coverage_uses_unique_days_not_sessions(tmp_path):
    workouts = [
        {"date": "2026-11-09", "type": "Running", "duration_minutes": 20},
        {"date": "2026-11-09", "type": "Strength", "duration_minutes": 50},
        {"date": "2026-11-07", "type": "Walking", "duration_minutes": 20},
    ]
    result = load_fitness(write(tmp_path, workouts), today=date(2026, 11, 9))
    assert result["active_days"] == 2
    assert result["rest_days"] == 5
    assert result["active_day_percent"] == 28.6


def test_empty_workout_week_reports_all_rest_days(tmp_path):
    result = load_fitness(write(tmp_path, []), today=date(2026, 11, 9))
    assert result["rest_days"] == 7
    assert result["active_day_percent"] == 0.0


def test_daily_workout_reports_full_week_coverage(tmp_path):
    workouts = [
        {"date": "2026-11-" + str(day).zfill(2), "type": "Walking", "duration_minutes": 15}
        for day in range(3, 10)
    ]
    result = load_fitness(write(tmp_path, workouts), today=date(2026, 11, 9))
    assert result["rest_days"] == 0
    assert result["active_day_percent"] == 100.0
