import plistlib
from pathlib import Path

from macos.service import LABEL, PORT, agent_path, service_config


def test_default_service_only_accepts_localhost(tmp_path: Path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    config = service_config(project, home)
    assert config["Label"] == LABEL
    assert config["ProgramArguments"][-2:] == ["--port", str(PORT)]
    assert config["ProgramArguments"][4:6] == ["--host", "127.0.0.1"]
    assert config["WorkingDirectory"] == str(project)
    assert config["RunAtLoad"] is True
    assert config["KeepAlive"] == {"SuccessfulExit": False}
    assert plistlib.loads(plistlib.dumps(config)) == config


def test_lan_service_requires_explicit_opt_in(tmp_path: Path):
    config = service_config(tmp_path / "project", tmp_path / "home", lan=True)
    assert config["ProgramArguments"][4:6] == ["--host", "0.0.0.0"]


def test_agent_is_installed_for_current_user(tmp_path: Path):
    path = agent_path(tmp_path)
    assert path == tmp_path / "Library" / "LaunchAgents" / (LABEL + ".plist")
