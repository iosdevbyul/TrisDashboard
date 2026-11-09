import json
from datetime import date
from backend.fitness import load_fitness


def load(tmp_path, workouts):
    p = tmp_path / "fitness.json"
    p.write_text(json.dumps({"workouts": workouts}), encoding="utf-8")
    return load_fitness(p, today=date(2026, 11, 9))


def test_time_share_distinct_from_workout_session_share(tmp_path):
    data = load(tmp_path, [
        {"date": "2026-11-09", "type": "Strength", "duration_minutes": 60},
        {"date": "2026-11-09", "type": "Running", "duration_minutes": 15},
        {"date": "2026-11-08", "type": "Running", "duration_minutes": 25},
    ])
    by_type = {x["type"]: x for x in data["activity_breakdown"]}
    assert by_type["Strength"]["time_share_percent"] == 60.0
    assert by_type["Strength"]["session_share_percent"] == 33.3
    assert by_type["Running"]["time_share_percent"] == 40.0


def test_zero_minute_sessions_do_not_divide_by_zero(tmp_path):
    data = load(tmp_path, [
        {"date": "2026-11-09", "type": "Walking", "duration_minutes": 0}
    ])
    assert data["activity_breakdown"][0]["time_share_percent"] == 0.0
