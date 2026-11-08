from pathlib import Path

from macos.server_cycle_check import check_restart


def test_uvicorn_server_recovers_after_clean_restart_without_external_providers():
    project = Path(__file__).resolve().parent.parent
    result = check_restart(project)
    assert result == {
        "passed": True,
        "first_start_passed": True,
        "restart_passed": True,
        "local_only": True,
        "provider_requests": 0,
    }
