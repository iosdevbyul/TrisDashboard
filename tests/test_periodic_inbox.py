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


def test_inbox_status_reports_readiness_without_private_paths(tmp_path):
    from macos.periodic_inbox import inspect, agent_path
    home = tmp_path / "Home"
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    output = tmp_path / "private" / "fitness.json"
    config = agent_config(tmp_path / "repo", home, inbox, output)
    agent = agent_path(home)
    agent.parent.mkdir(parents=True)
    agent.write_bytes(plistlib.dumps(config))
    (inbox / "waktrainer-dashboard-private-event.json").write_text("{}")
    status = inspect(home)
    assert status["installed"] is True
    assert status["configuration_valid"] is True
    assert status["inbox_available"] is True
    assert status["candidate_files"] == 1
    assert status["over_file_limit"] is False
    assert str(inbox) not in str(status)
    assert str(output) not in str(status)
    assert "private-event" not in str(status)


def test_inbox_status_missing_agent_is_safe(tmp_path):
    from macos.periodic_inbox import inspect
    assert inspect(tmp_path)["installed"] is False


def test_inbox_status_rejects_unexpected_arguments(tmp_path):
    from macos.periodic_inbox import inspect, agent_path
    home = tmp_path / "Home"
    agent = agent_path(home)
    agent.parent.mkdir(parents=True)
    agent.write_bytes(plistlib.dumps({
        "ProgramArguments": ["/bin/sh", "-c", "echo private"]
    }))
    status = inspect(home)
    assert status["installed"]
    assert status["configuration_valid"] is False
    assert "private" not in str(status)


def test_inbox_status_identifies_overfull_folder(tmp_path):
    from macos.periodic_inbox import inspect, agent_path
    from macos.receive_workouts import MAX_FILES
    home = tmp_path / "Home"
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    agent = agent_path(home)
    agent.parent.mkdir(parents=True)
    agent.write_bytes(plistlib.dumps(agent_config(
        tmp_path / "repo", home, inbox, tmp_path / "private" / "fitness.json"
    )))
    for index in range(MAX_FILES + 1):
        (inbox / ("waktrainer-dashboard-" + str(index) + ".json")).write_text("{}")
    status = inspect(home)
    assert status["candidate_files"] == MAX_FILES + 1
    assert status["over_file_limit"]


def test_scheduled_inbox_preserves_explicit_iana_timezone(tmp_path):
    from macos.periodic_inbox import inspect, agent_path
    home = tmp_path / "Home"
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    output = tmp_path / "private" / "fitness.json"
    config = agent_config(tmp_path / "repo", home, inbox, output,
                          timezone_name="Asia/Seoul")
    assert config["ProgramArguments"][-2:] == ["--timezone", "Asia/Seoul"]
    agent = agent_path(home)
    agent.parent.mkdir(parents=True)
    agent.write_bytes(plistlib.dumps(config))
    status = inspect(home)
    assert status["configuration_valid"] is True
    assert status["timezone_configured"] is True
    assert str(inbox) not in str(status)


def test_scheduled_inbox_rejects_invalid_timezone(tmp_path):
    from macos.periodic_inbox import inspect, agent_path
    home = tmp_path / "Home"
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    output = tmp_path / "private" / "fitness.json"
    with pytest.raises(ValueError, match="timezone"):
        agent_config(tmp_path / "repo", home, inbox, output,
                     timezone_name="Mars/Phobos")
    config = agent_config(tmp_path / "repo", home, inbox, output)
    config["ProgramArguments"].extend(["--timezone", "Mars/Phobos"])
    agent = agent_path(home)
    agent.parent.mkdir(parents=True)
    agent.write_bytes(plistlib.dumps(config))
    status = inspect(home)
    assert status["configuration_valid"] is False


def test_legacy_inbox_agent_without_timezone_remains_valid(tmp_path):
    from macos.periodic_inbox import inspect, agent_path
    home = tmp_path / "Home"
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    agent = agent_path(home)
    agent.parent.mkdir(parents=True)
    agent.write_bytes(plistlib.dumps(agent_config(
        tmp_path / "repo", home, inbox, tmp_path / "private" / "fitness.json"
    )))
    status = inspect(home)
    assert status["configuration_valid"] is True
    assert status["timezone_configured"] is False


def test_run_state_stores_only_counts_and_timestamp(tmp_path):
    from macos.periodic_inbox import write_run_state, read_run_state, state_path
    home = tmp_path / "Home"
    write_run_state(home, success=True, files=3, added=2)
    state = read_run_state(home)
    assert state["last_run_known"]
    assert state["last_run_success"]
    assert state["last_new_workouts"] == 2
    content = state_path(home).read_text()
    assert "fitness.json" not in content
    assert "error" not in content
    assert state_path(home).stat().st_mode & 0o077 == 0


def test_failed_run_does_not_reveal_exception_or_stale_success(tmp_path):
    from macos.periodic_inbox import write_run_state, read_run_state
    write_run_state(tmp_path, success=True, files=2, added=5)
    write_run_state(tmp_path, success=False)
    state = read_run_state(tmp_path)
    assert state["last_run_success"] is False
    assert state["last_new_workouts"] is None


def test_corrupted_status_file_returns_unknown(tmp_path):
    from macos.periodic_inbox import read_run_state, state_path
    file = state_path(tmp_path)
    file.parent.mkdir(parents=True)
    file.write_text("invalid JSON")
    assert read_run_state(tmp_path) == {"last_run_known": False}
