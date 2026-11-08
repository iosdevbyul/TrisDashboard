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
        "python_ready": True, "venv_ready": True, "server_reachable": False,
        "settings_ready": True, "inbox_agent_installed": False,
        "inbox_last_run_known": False,
        "deployment_ready": True,
        "unmet_requirements": [],
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


def test_strict_deployment_requires_server_if_requested(tmp_path):
    report = readiness(tmp_path, tmp_path, mac_check=mac_ok,
                       inbox_check=inbox_missing, require_server=True)
    assert not report["summary"]["deployment_ready"]
    assert report["summary"]["unmet_requirements"] == ["server"]


def test_strict_inbox_requires_agent_configuration(tmp_path):
    report = readiness(tmp_path, tmp_path, mac_check=mac_ok,
                       inbox_check=inbox_missing, require_inbox=True)
    assert not report["summary"]["deployment_ready"]
    assert "inbox-configuration" in report["summary"]["unmet_requirements"]


def test_recent_inbox_validates_time_and_success(tmp_path):
    from datetime import datetime, timezone, timedelta
    now = datetime(2026, 11, 8, 9, tzinfo=timezone.utc)
    good = {
        "installed": True, "configuration_valid": True,
        "inbox_available": True, "last_run_success": True,
        "last_run_utc": (now - timedelta(minutes=25)).isoformat(),
    }
    ok = readiness(tmp_path, tmp_path, mac_check=mac_ok,
                   inbox_check=lambda home: good,
                   require_recent_inbox=True, now=now)
    assert ok["summary"]["deployment_ready"]
    late = dict(good, last_run_utc=(now - timedelta(hours=2)).isoformat())
    failed = readiness(tmp_path, tmp_path, mac_check=mac_ok,
                       inbox_check=lambda home: late,
                       require_recent_inbox=True, now=now)
    assert failed["summary"]["unmet_requirements"] == ["inbox-last-run"]
    bad = dict(good, last_run_success=False)
    failed2 = readiness(tmp_path, tmp_path, mac_check=mac_ok,
                        inbox_check=lambda home: bad,
                        require_recent_inbox=True, now=now)
    assert "inbox-last-run" in failed2["summary"]["unmet_requirements"]


def test_strict_mode_only_exposes_safe_failure_identifiers(tmp_path):
    status = {
        "installed": True, "configuration_valid": True,
        "inbox_available": True, "last_run_success": True,
        "last_run_utc": "not-a-date",
    }
    report = readiness(tmp_path, tmp_path, mac_check=mac_ok,
                       inbox_check=lambda home: status,
                       require_recent_inbox=True)
    assert report["summary"]["unmet_requirements"] == ["inbox-last-run"]
    assert "private" not in str(report["summary"]).lower()


def test_missing_virtual_environment_is_not_ready_even_with_supported_python(tmp_path):
    def mac_without_venv(project, home):
        return dict(mac_ok(project, home), venv_created=False)
    result = readiness(tmp_path, tmp_path, mac_check=mac_without_venv,
                       inbox_check=inbox_missing)
    assert result["summary"]["python_ready"] is True
    assert result["summary"]["venv_ready"] is False
    assert result["summary"]["deployment_ready"] is False
    assert result["summary"]["unmet_requirements"] == ["venv"]


def test_healthy_virtual_environment_passes_base_readiness(tmp_path):
    result = readiness(tmp_path, tmp_path, mac_check=mac_ok,
                       inbox_check=inbox_missing)
    assert result["summary"]["venv_ready"] is True
    assert result["summary"]["deployment_ready"] is True
