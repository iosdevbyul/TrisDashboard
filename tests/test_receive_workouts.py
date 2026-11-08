import json

import pytest

from macos.receive_workouts import receive


def write_export(directory, name, session_id, seconds=600):
    path = directory / ("waktrainer-dashboard-" + name + ".json")
    path.write_text(json.dumps({"schema_version": 2, "sessions": [{
        "session_id": session_id,
        "started_at": "2026-11-08T08:15:00+09:00",
        "activity_type": "running",
        "duration_seconds": seconds,
        "distance_meters": 2500,
    }]}))
    return path


def test_inbox_previews_all_shared_files_without_writing(tmp_path):
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    write_export(inbox, "first", "a")
    write_export(inbox, "second", "b")
    output = tmp_path / "private" / "fitness.json"
    info = receive(inbox, output)
    assert info["files"] == 2
    assert info["new"] == 2
    assert info["total"] == 2
    assert not output.parent.exists()


def test_inbox_import_is_idempotent_and_atomic(tmp_path):
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    write_export(inbox, "first", "a")
    write_export(inbox, "second", "b")
    output = tmp_path / "private" / "fitness.json"
    first = receive(inbox, output, apply=True)
    assert first["written"] and first["new"] == 2
    before = output.read_bytes()
    again = receive(inbox, output, apply=True)
    assert again["new"] == 0 and not again["written"]
    assert output.read_bytes() == before


def test_inbox_conflicting_same_session_id_preserves_history(tmp_path):
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    write_export(inbox, "one", "same-id", 600)
    output = tmp_path / "fitness.json"
    receive(inbox, output, apply=True)
    original = output.read_bytes()
    write_export(inbox, "two", "same-id", 900)
    with pytest.raises(ValueError, match="Conflicting"):
        receive(inbox, output, apply=True)
    assert output.read_bytes() == original


def test_inbox_rejects_symlink_to_other_data(tmp_path):
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    private = tmp_path / "unrelated.json"
    private.write_text("{}")
    (inbox / "waktrainer-dashboard-link.json").symlink_to(private)
    with pytest.raises(ValueError, match="Unsafe"):
        receive(inbox, tmp_path / "out.json", apply=True)
    assert not (tmp_path / "out.json").exists()


def test_inbox_leaves_unmatched_files_untouched(tmp_path):
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    ignored = inbox / "other-private.json"
    ignored.write_text('{"private":true}')
    result = receive(inbox, tmp_path / "out.json", apply=True)
    assert result["files"] == 0 and result["new"] == 0
    assert ignored.read_text() == '{"private":true}'


def test_overlapping_airdrop_exports_with_same_workout_are_deduplicated(tmp_path):
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    write_export(inbox, "one", "same-id")
    write_export(inbox, "two", "same-id")
    output = tmp_path / "fitness.json"
    first = receive(inbox, output, apply=True)
    assert first["files"] == 2
    assert first["new"] == 1
    assert first["duplicates"] == 1
    assert len(json.loads(output.read_text())["workouts"]) == 1
    assert receive(inbox, output, apply=True)["new"] == 0


def test_many_overlapping_exports_only_count_unique_sessions(tmp_path):
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    source_sessions = [{
        "session_id": "id-" + str(i),
        "started_at": "2026-11-08T08:15:00+09:00",
        "activity_type": "running", "duration_seconds": 600,
        "distance_meters": 2500
    } for i in range(200)]
    for name in ("first", "second", "third"):
        (inbox / ("waktrainer-dashboard-" + name + ".json")).write_text(
            json.dumps({"schema_version": 2, "sessions": source_sessions}))
    output = tmp_path / "private" / "fitness.json"
    result = receive(inbox, output, apply=True)
    assert result["incoming"] == 600
    assert result["new"] == 200
    assert result["duplicates"] == 400
    assert len(json.loads(output.read_text())["workouts"]) == 200
    assert receive(inbox, output, apply=True)["new"] == 0


def test_received_utc_exports_use_explicit_seoul_calendar_date(tmp_path):
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    source = write_export(inbox, "utc-date", "seoul-id")
    payload = json.loads(source.read_text())
    payload["sessions"][0]["started_at"] = "2026-11-07T16:30:00Z"
    source.write_text(json.dumps(payload))
    target = tmp_path / "fitness.json"
    result = receive(inbox, target, apply=True, timezone_name="Asia/Seoul")
    assert result["new"] == 1
    assert json.loads(target.read_text())["workouts"][0]["date"] == "2026-11-08"


def test_oversized_inbox_file_does_not_change_history(tmp_path):
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    target = tmp_path / "private" / "fitness.json"
    write_export(inbox, "original", "session-1")
    receive(inbox, target, apply=True)
    original = target.read_bytes()
    (inbox / "waktrainer-dashboard-oversized.json").write_bytes(
        b" " * (128 * 1024 + 1))
    with pytest.raises(ValueError, match="too large"):
        receive(inbox, target, apply=True)
    assert target.read_bytes() == original


def test_oversized_inbox_file_fails_preview_without_creating_output(tmp_path):
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    (inbox / "waktrainer-dashboard-oversized.json").write_bytes(
        b" " * (128 * 1024 + 1))
    target = tmp_path / "private" / "fitness.json"
    with pytest.raises(ValueError, match="too large"):
        receive(inbox, target)
    assert not target.parent.exists()
