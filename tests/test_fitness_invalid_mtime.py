import json
from pathlib import Path
from types import SimpleNamespace
from backend.fitness import fitness


def test_unrepresentable_workout_mtime_fails_closed(tmp_path, monkeypatch):
    path = tmp_path / "workouts.json"
    path.write_text(json.dumps({"workouts": []}), encoding="utf-8")
    original_stat = Path.stat
    def invalid_stat(self, *args, **kwargs):
        result = original_stat(self, *args, **kwargs)
        if self == path:
            return SimpleNamespace(st_size=result.st_size, st_mtime=1e100)
        return result
    monkeypatch.setattr(Path, "stat", invalid_stat)
    monkeypatch.setenv("TRIS_FITNESS_FILE", str(path))
    assert fitness() == {"available": False, "configured": True, "stale": True}
