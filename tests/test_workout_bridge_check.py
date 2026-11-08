import json

from macos.workout_bridge_check import check_bridge


def test_full_synthetic_waktrainer_to_dashboard_import():
    result = check_bridge()
    assert result == {
        "passed": True, "schema_version": 2, "source_files": 2,
        "unique_sessions": 1, "duplicate_sessions_skipped": 1,
        "repeat_import_safe": True, "timezone_verified": True,
        "private_files_used": False, "network_requests": 0,
    }


def test_synthetic_workout_acceptance_does_not_expose_private_values():
    result = json.dumps(check_bridge())
    assert "session_id" not in result
    assert "started_at" not in result
    assert "/private/" not in result
    assert "TRIS_FITNESS_FILE" not in result
