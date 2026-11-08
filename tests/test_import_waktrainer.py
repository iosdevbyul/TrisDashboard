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


@pytest.mark.parametrize("version", [0, 3, "1", None])
def test_reject_unknown_schema_version(tmp_path, version):
    with pytest.raises(ValueError):
        parse_export(export(tmp_path, [], version=version))


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, 90000])
def test_reject_invalid_duration(tmp_path, value):
    source = export(tmp_path, [{"started_at": "2026-11-08T08:10:00+09:00",
                               "activity_type": "running", "duration_seconds": value}])
    with pytest.raises(ValueError):
        parse_export(source)


def test_merge_import_is_idempotent(tmp_path):
    first = export(tmp_path, [{"started_at": "2026-11-08T08:10:00+09:00",
                               "activity_type": "running", "duration_seconds": 2700,
                               "distance_meters": 7250}])
    output = tmp_path / "history.json"
    assert import_export(first, output)["added"] == 1
    assert import_export(first, output, merge=True)["added"] == 0
    assert len(json.loads(output.read_text())["workouts"]) == 1


def test_merge_preserves_other_sessions(tmp_path):
    source = export(tmp_path, [{"started_at": "2026-11-08T08:10:00+09:00",
                                "activity_type": "running", "duration_seconds": 600}])
    output = tmp_path / "history.json"
    output.write_text(json.dumps({"workouts": [
        {"date": "2026-11-07", "type": "Strength", "duration_minutes": 50, "distance_km": 0}
    ]}))
    result = import_export(source, output, merge=True)
    assert result["added"] == 1
    assert result["sessions"] == 2
    assert len(json.loads(output.read_text())["workouts"]) == 2


def test_invalid_previous_history_never_overwritten(tmp_path):
    source = export(tmp_path, [{"started_at": "2026-11-08T08:10:00+09:00",
                               "activity_type": "running", "duration_seconds": 600}])
    output = tmp_path / "history.json"
    output.write_text("invalid")
    with pytest.raises(ValueError):
        import_export(source, output, merge=True)
    assert output.read_text() == "invalid"


def test_force_merge_conflict_rejected(tmp_path):
    source = export(tmp_path, [])
    with pytest.raises(ValueError, match="cannot"):
        import_export(source, tmp_path / "output.json", merge=True, force=True)


def test_failure_cannot_overwrite_previous_workouts(tmp_path):
    source = export(tmp_path, [{"started_at": "2026-11-08T08:10:00+09:00",
                               "activity_type": "undefined", "duration_seconds": 50}])
    destination = tmp_path / "fitness.json"
    destination.write_text("old")
    with pytest.raises(ValueError):
        import_export(source, destination, force=True)
    assert destination.read_text() == "old"


def test_v2_preserves_stable_session_id_and_distinguishes_same_metrics(tmp_path):
    source = export(tmp_path, [
        {"session_id": "ios-workout-001", "started_at": "2026-11-08T09:00:00+09:00",
         "activity_type": "running", "duration_seconds": 3600, "distance_meters": 10000},
        {"session_id": "ios-workout-002", "started_at": "2026-11-08T12:00:00+09:00",
         "activity_type": "running", "duration_seconds": 3600, "distance_meters": 10000},
    ], version=2)
    dest = tmp_path / "fitness.json"
    imported = import_export(source, dest)
    assert imported["added"] == 2
    assert import_export(source, dest, merge=True)["added"] == 0
    records = json.loads(dest.read_text())["workouts"]
    assert {record["session_id"] for record in records} == {"ios-workout-001", "ios-workout-002"}


def test_v2_duplicate_ids_rejected(tmp_path):
    session = {"session_id": "same-id", "started_at": "2026-11-08T09:00:00+09:00",
               "activity_type": "running", "duration_seconds": 600}
    with pytest.raises(ValueError, match="Duplicate session"):
        parse_export(export(tmp_path, [session, session], version=2))


def test_v2_rejects_missing_or_invalid_id(tmp_path):
    session = {"started_at": "2026-11-08T09:00:00+09:00",
               "activity_type": "running", "duration_seconds": 600}
    with pytest.raises(ValueError, match="session_id"):
        parse_export(export(tmp_path, [session], version=2))
    session["session_id"] = "invalid id /"
    with pytest.raises(ValueError, match="session_id"):
        parse_export(export(tmp_path, [session], version=2))


def test_legacy_v1_export_still_supported(tmp_path):
    data = parse_export(export(tmp_path, [
        {"started_at": "2026-11-08T08:10:00+09:00",
         "activity_type": "walking", "duration_seconds": 1200}
    ]))
    assert "session_id" not in data["workouts"][0]


def test_v2_conflicting_same_id_cannot_silently_discard_changed_measurement(tmp_path):
    first = export(tmp_path, [{
        "session_id": "stable-01", "started_at": "2026-11-08T09:00:00+09:00",
        "activity_type": "running", "duration_seconds": 1200,
        "distance_meters": 3000,
    }], version=2)
    output = tmp_path / "history.json"
    import_export(first, output)
    original = output.read_bytes()
    export(tmp_path, [{
        "session_id": "stable-01", "started_at": "2026-11-08T09:00:00+09:00",
        "activity_type": "running", "duration_seconds": 1500,
        "distance_meters": 3500,
    }], version=2)
    with pytest.raises(ValueError, match="Conflicting workout session ID"):
        import_export(first, output, merge=True)
    assert output.read_bytes() == original


def test_v2_two_different_ids_same_metrics_are_preserved(tmp_path):
    path = export(tmp_path, [
        {"session_id": "a", "started_at": "2026-11-08T09:00:00+09:00",
         "activity_type": "running", "duration_seconds": 1200},
        {"session_id": "b", "started_at": "2026-11-08T09:00:00+09:00",
         "activity_type": "running", "duration_seconds": 1200},
    ], version=2)
    output = tmp_path / "history.json"
    assert import_export(path, output)["added"] == 2
    assert import_export(path, output, merge=True)["added"] == 0


def test_v1_duplicate_measurements_rejected_instead_of_double_counted(tmp_path):
    workout = {"started_at": "2026-11-08T09:00:00+09:00",
               "activity_type": "running", "duration_seconds": 1200}
    with pytest.raises(ValueError, match="Duplicate legacy"):
        parse_export(export(tmp_path, [workout, workout]))


def test_duplicate_merge_does_not_rewrite_existing_file(tmp_path):
    source = export(tmp_path, [{
        "session_id": "stable-23", "started_at": "2026-11-08T09:00:00+09:00",
        "activity_type": "running", "duration_seconds": 1200
    }], version=2)
    target = tmp_path / "history.json"
    assert import_export(source, target)["written"] is True
    stat = target.stat()
    data = target.read_bytes()
    second = import_export(source, target, merge=True)
    assert second == {"sessions": 1, "added": 0, "written": False}
    assert target.read_bytes() == data
    assert target.stat().st_mtime_ns == stat.st_mtime_ns
    assert (tmp_path / "history.json.lock").stat().st_mode & 0o077 == 0


def test_bad_import_releases_sidecar_lock(tmp_path):
    source = export(tmp_path, [{
        "session_id": "bad-id", "started_at": "2026-11-08T09:00:00+09:00",
        "activity_type": "incorrect", "duration_seconds": 1200
    }], version=2)
    target = tmp_path / "history.json"
    with pytest.raises(ValueError):
        import_export(source, target)
    export(tmp_path, [{
        "session_id": "good-id", "started_at": "2026-11-08T09:00:00+09:00",
        "activity_type": "walking", "duration_seconds": 1200
    }], version=2)
    assert import_export(source, target)["added"] == 1


def test_dry_run_has_no_lock_or_directory_side_effects(tmp_path):
    source = export(tmp_path, [{"session_id": "dry-01",
                               "started_at": "2026-11-08T09:00:00+09:00",
                               "activity_type": "walking",
                               "duration_seconds": 600}], version=2)
    target = tmp_path / "new-private-folder" / "history.json"
    result = import_export(source, target, dry_run=True)
    assert result["written"] is False
    assert not target.parent.exists()


def test_import_rejects_world_readable_sidecar_lock(tmp_path):
    source = export(tmp_path, [{"session_id": "private-01",
                               "started_at": "2026-11-08T09:00:00+09:00",
                               "activity_type": "walking",
                               "duration_seconds": 600}], version=2)
    lock = tmp_path / "history.json.lock"
    lock.write_bytes(b"")
    lock.chmod(0o644)
    with pytest.raises(ValueError, match="owner-only"):
        import_export(source, tmp_path / "history.json")
    assert not (tmp_path / "history.json").exists()


def test_import_rejects_symlink_sidecar_lock(tmp_path):
    source = export(tmp_path, [{"session_id": "private-02",
                               "started_at": "2026-11-08T09:00:00+09:00",
                               "activity_type": "walking",
                               "duration_seconds": 600}], version=2)
    victim = tmp_path / "victim.txt"
    victim.write_text("unrelated file")
    (tmp_path / "history.json.lock").symlink_to(victim)
    with pytest.raises((OSError, ValueError)):
        import_export(source, tmp_path / "history.json")
    assert victim.read_text() == "unrelated file"


def test_utc_waktrainer_export_can_use_seoul_calendar_day(tmp_path):
    source = export(tmp_path, [{
        "session_id": "late-evening", "started_at": "2026-11-07T16:30:00Z",
        "activity_type": "walking", "duration_seconds": 1200
    }], version=2)
    assert parse_export(source)["workouts"][0]["date"] == "2026-11-07"
    assert parse_export(source, timezone_name="Asia/Seoul")["workouts"][0]["date"] == "2026-11-08"
    target = tmp_path / "history.json"
    result = import_export(source, target, timezone_name="Asia/Seoul")
    assert result["added"] == 1
    assert json.loads(target.read_text())["workouts"][0]["date"] == "2026-11-08"


def test_unknown_import_timezone_rejected_without_output(tmp_path):
    source = export(tmp_path, [{
        "session_id": "fail-zone", "started_at": "2026-11-07T16:30:00Z",
        "activity_type": "walking", "duration_seconds": 1200
    }], version=2)
    target = tmp_path / "fitness.json"
    with pytest.raises(ValueError, match="timezone"):
        import_export(source, target, dry_run=True, timezone_name="Mars/Phobos")
    assert not target.exists()


@pytest.mark.parametrize("session_id", ["ｓｅｓｓｉｏｎ", "abcé", "abc١"])
def test_v2_non_ascii_session_ids_rejected_before_import(tmp_path, session_id):
    source = export(tmp_path, [{
        "session_id": session_id, "started_at": "2026-11-08T09:00:00+09:00",
        "activity_type": "walking", "duration_seconds": 600,
    }], version=2)
    with pytest.raises(ValueError, match="session_id"):
        parse_export(source)


@pytest.mark.parametrize("raw", [
    '{"schema_version":2,"schema_version":1,"sessions":[]}',
    '{"schema_version":2,"sessions":[{"session_id":"a","session_id":"b"}]}',
    '{"schema_version":2,"sessions":[],"metadata":NaN}',
    '{"schema_version":2,"sessions":[],"metadata":Infinity}',
])
def test_workout_export_rejects_duplicate_or_nonstandard_json(tmp_path, raw):
    file = tmp_path / "ambiguous-export.json"
    file.write_text(raw)
    with pytest.raises(ValueError):
        parse_export(file)
