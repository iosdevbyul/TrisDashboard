import json

import pytest

from macos.import_waktrainer import import_export, parse_export


def export(tmp_path, sessions, version=1):
    path = tmp_path / "waktrainer-export.json"
    path.write_text(json.dumps({"schema_version": version, "sessions": sessions}))
    return path


def test_waktrainer_bridge_maps_units_and_local_date(tmp_path):
    source = export(tmp_path, [{"started_at": "2026-11-08T08:10:00+09:00",
                               "activity_type": "running", "duration_seconds": 2700,
                               "distance_meters": 7250}])
    result = parse_export(source)
    assert result["workouts"] == [{"date": "2026-11-08", "type": "Running",
                                   "duration_minutes": 45.0, "distance_km": 7.25}]
    destination = tmp_path / "private" / "fitness.json"
    assert import_export(source, destination)["written"]
    assert json.loads(destination.read_text()) == result
    assert destination.stat().st_mode & 0o077 == 0


def test_timezone_is_required(tmp_path):
    source = export(tmp_path, [{"started_at": "2026-11-08T08:00:00",
                               "activity_type": "walking", "duration_seconds": 60}])
    with pytest.raises(ValueError, match="timezone"):
        parse_export(source)


@pytest.mark.parametrize("version", [0, 2, "1", None])
def test_reject_unknown_schema_version(tmp_path, version):
    with pytest.raises(ValueError):
        parse_export(export(tmp_path, [], version=version))


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, 90000])
def test_reject_invalid_duration(tmp_path, value):
    source = export(tmp_path, [{"started_at": "2026-11-08T08:10:00+09:00",
                               "activity_type": "running", "duration_seconds": value}])
    with pytest.raises(ValueError):
        parse_export(source)


def test_failure_cannot_overwrite_previous_workouts(tmp_path):
    source = export(tmp_path, [{"started_at": "2026-11-08T08:10:00+09:00",
                               "activity_type": "undefined", "duration_seconds": 50}])
    destination = tmp_path / "fitness.json"
    destination.write_text("old")
    with pytest.raises(ValueError):
        import_export(source, destination, force=True)
    assert destination.read_text() == "old"
