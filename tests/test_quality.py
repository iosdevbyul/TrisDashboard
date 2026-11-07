from datetime import datetime, timezone, timedelta
import pytest
from backend.quality import snapshot_quality

NOW = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)


def test_outdated_manual_snapshot():
    result = snapshot_quality(NOW - timedelta(hours=80), NOW)
    assert result == {"age_hours": 80.0, "outdated": True, "threshold_hours": 72}


def test_recent_snapshot_is_current():
    assert snapshot_quality(NOW - timedelta(hours=1), NOW)["outdated"] is False


def test_future_snapshot_rejected():
    with pytest.raises(ValueError):
        snapshot_quality(NOW + timedelta(days=1), NOW)


def test_timezone_required():
    with pytest.raises(ValueError):
        snapshot_quality(datetime(2026, 11, 8), NOW)
