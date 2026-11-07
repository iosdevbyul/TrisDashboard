from macos.doctor import inspect


def test_doctor_ready(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    python = project / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()
    agent = home / "Library" / "LaunchAgents" / "ai.tris.dashboard.plist"
    agent.parent.mkdir(parents=True)
    agent.touch()
    result = inspect(project, home, probe=lambda: True, python_version=(3, 11, 0))
    assert result == {
        "python_supported": True,
        "venv_created": True,
        "launch_agent_installed": True,
        "local_server_reachable": True,
    }


def test_doctor_offline_has_no_sensitive_data(tmp_path):
    result = inspect(tmp_path / "project", tmp_path / "home",
                     probe=lambda: False, python_version=(3, 10, 9))
    assert not any(result.values())
    assert "token" not in str(result).lower()


def test_shell_bootstrap_is_explicit_about_lan_access():
    from pathlib import Path
    script = (Path(__file__).resolve().parent.parent / "scripts" / "setup-mac.sh").read_text()
    assert "python3 -m venv .venv" in script
    assert "install --lan" in script
    assert "python -m macos.service install --lan" not in script
