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
