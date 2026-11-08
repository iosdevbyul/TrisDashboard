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
    assert "\\npython -m macos.service install --lan" not in script


def test_doctor_keychain_flag_does_not_show_secret_text():
    from pathlib import Path
    script = (Path(__file__).resolve().parent.parent / "macos" / "doctor.py").read_text()
    assert "credentials_present" in script
    assert "credential_status()" in script


def test_doctor_health_probe_limits_response_and_verifies_content(monkeypatch):
    from macos import doctor
    class Response:
        status = 200
        def __init__(self, body):
            self.body = body
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, amount):
            assert amount == 513
            return self.body[:amount]
    monkeypatch.setattr(doctor, "urlopen", lambda url, timeout: Response(b" " * 513))
    assert doctor.probe_server() is False
    monkeypatch.setattr(doctor, "urlopen", lambda url, timeout: Response(b'{"status":"ok"}'))
    assert doctor.probe_server() is True
    monkeypatch.setattr(doctor, "urlopen", lambda url, timeout: Response(b'{"status":"unexpected"}'))
    assert doctor.probe_server() is False
