import json
import os
import time
from datetime import date
from backend.fitness import load_fitness


def test_future_dated_workout_export_does_not_look_fresh(tmp_path):
    path = tmp_path / "workouts.json"
    path.write_text(json.dumps({"workouts": []}), encoding="utf-8")
    future = time.time() + 3600
    os.utime(path, (future, future))
    result = load_fitness(path, today=date(2026, 11, 9))
    assert result["file_mtime_in_future"] is True
    assert result["stale"] is True
    assert result["available"] is True


def test_normal_workout_file_does_not_raise_future_warning(tmp_path):
    path = tmp_path / "workouts.json"
    path.write_text(json.dumps({"workouts": []}), encoding="utf-8")
    result = load_fitness(path, today=date(2026, 11, 9))
    assert result["file_mtime_in_future"] is False
    assert result["stale"] is False
