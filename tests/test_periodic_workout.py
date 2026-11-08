import json
import plistlib

import pytest

from macos.periodic_workout import (
    INTERVAL_SECONDS, LABEL, agent_config, import_once, safe_path,
)


def test_missing_export_is_not_failure(tmp_path):
    output = tmp_path / "history.json"
    assert import_once(tmp_path / "missing.json", output) == {
        "state": "waiting-for-export", "added": 0}
    assert not output.exists()


def test_periodic_import_does_not_repeat_workout(tmp_path):
    source = tmp_path / "latest-export.json"
    source.write_text(json.dumps({"schema_version": 1, "sessions": [
        {"started_at": "2026-11-08T09:00:00+09:00",
         "activity_type": "walking", "duration_seconds": 1800}
    ]}))
    output = tmp_path / "history.json"
    assert import_once(source, output)["added"] == 1
    assert import_once(source, output)["added"] == 0
    assert len(json.loads(output.read_text())["workouts"]) == 1


def test_agent_config_runs_every_fifteen_minutes(tmp_path):
    agent = agent_config(tmp_path / "repo", tmp_path / "home",
                         tmp_path / "in.json", tmp_path / "out.json")
    assert agent["Label"] == LABEL
    assert agent["StartInterval"] == INTERVAL_SECONDS == 900
    assert agent["ProgramArguments"][1:4] == ["-m", "macos.periodic_workout", "run-once"]
    assert plistlib.loads(plistlib.dumps(agent)) == agent
    assert "KeepAlive" not in agent


def test_import_paths_must_not_be_in_source_repository():
    from pathlib import Path
    repo = Path(__file__).resolve().parent.parent
    with pytest.raises(ValueError):
        safe_path(repo / "frontend" / "private.json")
    with pytest.raises(ValueError):
        safe_path(repo / "tests" / "private.json")


def test_import_once_rejects_identical_source_and_destination(tmp_path):
    export = tmp_path / "export.json"
    export.write_text('{"schema_version":1,"sessions":[]}')
    with pytest.raises(ValueError, match="must differ"):
        import_once(export, export)
    assert export.read_text() == '{"schema_version":1,"sessions":[]}'
