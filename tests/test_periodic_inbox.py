import json
import os
import plistlib

import pytest

from macos.periodic_inbox import (
    LABEL, INTERVAL_SECONDS, agent_config, agent_path, private_inbox,
)
from macos.receive_workouts import receive


def test_inbox_launchagent_interval_and_read_only_project_config(tmp_path):
    home, project, inbox = tmp_path / "home", tmp_path / "project", tmp_path / "Downloads"
    agent = agent_config(project, home, inbox, home / "private" / "fitness.json")
    assert agent["Label"] == LABEL
    assert agent["StartInterval"] == INTERVAL_SECONDS == 900
    assert agent["ProgramArguments"][1:4] == ["-m", "macos.periodic_inbox", "run-once"]
    assert agent["ProgramArguments"][4:6] == ["--directory", str(inbox)]
    assert plistlib.loads(plistlib.dumps(agent)) == agent
    assert "KeepAlive" not in agent


def test_inbox_path_rejects_symlinks_and_repository_folders(tmp_path):
    folder = tmp_path / "Downloads"
    folder.mkdir()
    assert private_inbox(folder) == folder.resolve()
    linked = tmp_path / "Linked"
    linked.symlink_to(folder, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        private_inbox(linked)
    from pathlib import Path
    repository = Path(__file__).resolve().parent.parent
    with pytest.raises(ValueError, match="outside"):
        private_inbox(repository / "frontend")


def test_optional_inbox_remains_inert_until_workout_file_arrives(tmp_path):
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    output = tmp_path / "private" / "fitness.json"
    assert receive(inbox, output, apply=True)["new"] == 0
    assert not output.exists()
    (inbox / "waktrainer-dashboard-test.json").write_text(json.dumps({
        "schema_version": 2, "sessions": [{
            "session_id": "wkt-001", "started_at": "2026-11-08T09:00:00+09:00",
            "activity_type": "walking", "duration_seconds": 900
        }]
    }))
    assert receive(inbox, output, apply=True)["new"] == 1
    assert receive(inbox, output, apply=True)["new"] == 0
    assert len(json.loads(output.read_text())["workouts"]) == 1
