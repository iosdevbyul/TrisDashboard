from datetime import datetime, timezone
import pytest
from backend.quality import snapshot_quality


NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)


def test_extreme_freshness_threshold_rejected():
    for limit in (87601, 1e308):
        with pytest.raises(ValueError, match="Invalid freshness threshold"):
            snapshot_quality(NOW, NOW, limit_hours=limit)


def test_ten_year_freshness_threshold_still_supported():
    assert snapshot_quality(NOW, NOW, limit_hours=87600)["threshold_hours"] == 87600
