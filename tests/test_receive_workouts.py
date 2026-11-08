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
