from macos.readiness import readiness


def mac_ok(project, home):
    return {
        "python_supported": True, "venv_created": True,
        "launch_agent_installed": False, "local_server_reachable": False,
    }


def inbox_missing(home):
    return {
        "installed": False, "configuration_valid": False,
        "last_run_known": False, "candidate_files": 0,
    }


def test_unified_readiness_reports_optional_components_without_false_failure(tmp_path):
    result = readiness(tmp_path, tmp_path, mac_check=mac_ok,
                       inbox_check=inbox_missing)
    assert result["summary"] == {
        "python_ready": True, "server_reachable": False,
        "settings_ready": True, "inbox_agent_installed": False,
        "inbox_last_run_known": False,
    }
    assert result["settings"] == {"checked": False}


def test_unified_readiness_reports_private_file_error_without_path(tmp_path):
    private_path = tmp_path / "hidden-password-data.json"
    def settings_invalid(path):
        return {"settings": "valid", "files": {"fitness": "invalid"}, "ready": False}
    result = readiness(tmp_path, tmp_path, settings=private_path,
                       mac_check=mac_ok, inbox_check=inbox_missing,
                       settings_check=settings_invalid)
    assert not result["summary"]["settings_ready"]
    assert result["settings"]["file_states"]["fitness"] == "invalid"
    assert str(private_path) not in str(result)
    assert "password" not in str(result)


def test_unified_readiness_does_not_touch_external_services(tmp_path):
    called = []
    def mac(project, home):
        called.append("localhost")
        return mac_ok(project, home)
    def inbox(home):
        called.append("local-agent")
        return inbox_missing(home)
    result = readiness(tmp_path, tmp_path, mac_check=mac,
                       inbox_check=inbox)
    assert called == ["localhost", "local-agent"]
    assert "TRIS_TWELVEDATA_API_KEY" not in str(result)
