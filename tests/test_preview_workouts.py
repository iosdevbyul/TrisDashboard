import json
import pytest

from macos.preview_workouts import preview
from macos.import_waktrainer import import_export


def export(tmp_path, sessions):
    source = tmp_path / "waktrainer-export.json"
    source.write_text(json.dumps({"schema_version": 2, "sessions": sessions}))
    return source


def session(session_id, seconds=600):
    return {"session_id": session_id, "started_at": "2026-11-08T08:00:00Z",
            "activity_type": "running", "duration_seconds": seconds, "distance_meters": 3000}


def test_preview_reports_duplicates_and_does_not_write(tmp_path):
    source = export(tmp_path, [session("first"), session("second")])
    target = tmp_path / "history.json"
    import_export(source, target)
    previous, timestamp = target.read_bytes(), target.stat().st_mtime_ns
    result = preview(source, target)
    assert result == {"existing": 2, "incoming": 2, "new": 0, "duplicates": 2,
                      "total": 2, "earliest_day": "2026-11-08",
                      "latest_day": "2026-11-08", "written": False}
    assert target.read_bytes() == previous
    assert target.stat().st_mtime_ns == timestamp


def test_preview_new_export_does_not_create_directories(tmp_path):
    source = export(tmp_path, [session("first")])
    target = tmp_path / "not-created" / "history.json"
    assert preview(source, target)["new"] == 1
    assert not target.parent.exists()


def test_preview_rejects_same_id_different_workout(tmp_path):
    source = export(tmp_path, [session("first")])
    target = tmp_path / "history.json"
    import_export(source, target)
    export(tmp_path, [session("first", 1800)])
    before = target.read_bytes()
    with pytest.raises(ValueError, match="Conflicting"):
        preview(source, target)
    assert target.read_bytes() == before
