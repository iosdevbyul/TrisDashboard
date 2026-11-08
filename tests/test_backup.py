import json
import os
from datetime import datetime, timezone, timedelta

import pytest

from macos.backup import backup, restore, validate_backup


def fixture_files(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    holdings = private / "portfolio.json"
    holdings.write_text(json.dumps({
        "as_of": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "positions": [{"symbol": "JEPQ", "currency": "USD", "quantity": 2}],
    }))
    agenda = private / "agenda.json"
    agenda.write_text(json.dumps({"events": [{"date": "2026-11-08", "title": "A private event"}]}))
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"TRIS_PORTFOLIO_FILE": str(holdings),
                                    "TRIS_AGENDA_FILE": str(agenda)}))
    return settings, holdings, agenda


def test_backup_creates_private_verified_snapshot(tmp_path):
    settings, holdings, agenda = fixture_files(tmp_path)
    output = tmp_path / "snapshots" / "backup-001"
    result = backup(settings, output)
    assert result == {"backed_up": 2, "created": True}
    assert len(validate_backup(output)) == 2
    assert output.stat().st_mode & 0o077 == 0
    assert (output / "portfolio.json").stat().st_mode & 0o077 == 0
    assert "JEPQ" not in (output / "manifest.json").read_text()
    with pytest.raises(ValueError, match="already exists"):
        backup(settings, output)


def test_restore_dry_run_and_explicit_restore(tmp_path):
    settings, holdings, agenda = fixture_files(tmp_path)
    output = tmp_path / "backup"
    original = holdings.read_bytes()
    backup(settings, output)
    holdings.write_text('{"as_of": "invalid", "positions": []}')
    assert restore(settings, output) == {"validated": 2, "restored": 0}
    assert holdings.read_text().startswith('{"as_of": "invalid"')
    assert restore(settings, output, force=True) == {"validated": 2, "restored": 2}
    assert holdings.read_bytes() == original


def test_corrupted_backup_never_overwrites(tmp_path):
    settings, holdings, agenda = fixture_files(tmp_path)
    output = tmp_path / "backup"
    backup(settings, output)
    original = holdings.read_bytes()
    (output / "portfolio.json").write_text('{"positions": []}')
    with pytest.raises(ValueError, match="checksum"):
        restore(settings, output, force=True)
    assert holdings.read_bytes() == original


def test_backup_missing_configuration_rejected(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text("{}")
    with pytest.raises(ValueError, match="No private"):
        backup(settings, tmp_path / "backup")


def test_partial_replace_failure_rolls_back_all_data(tmp_path, monkeypatch):
    from macos import backup as module
    settings, holdings, agenda = fixture_files(tmp_path)
    snapshot = tmp_path / "snapshot"
    module.backup(settings, snapshot)
    holdings.write_text('{"as_of":"changed","positions":[]}')
    agenda.write_text('{"events":[{"date":"2026-11-08","title":"new local event"}]}')
    original_holdings, original_agenda = holdings.read_bytes(), agenda.read_bytes()
    original_replace = module.os.replace
    counter = {"value": 0}

    def fail_second_destination(src, dst):
        if str(src).find(".tris-restore-") != -1:
            counter["value"] += 1
            if counter["value"] == 2:
                raise OSError("simulated storage failure")
        return original_replace(src, dst)

    monkeypatch.setattr(module.os, "replace", fail_second_destination)
    with pytest.raises(OSError, match="simulated"):
        module.restore(settings, snapshot, force=True)
    assert holdings.read_bytes() == original_holdings
    assert agenda.read_bytes() == original_agenda


def test_restore_dry_run_also_validates_schema(tmp_path):
    settings, holdings, agenda = fixture_files(tmp_path)
    snapshot = tmp_path / "snapshot"
    backup(settings, snapshot)
    import hashlib
    malformed = b'{"positions":[]}'
    (snapshot / "portfolio.json").write_bytes(malformed)
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["portfolio"]["sha256"] = hashlib.sha256(malformed).hexdigest()
    manifest["files"]["portfolio"]["bytes"] = len(malformed)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises((ValueError, KeyError)):
        restore(settings, snapshot)


@pytest.mark.parametrize("metadata", [
    {"bytes": True, "sha256": "a" * 64},
    {"bytes": -1, "sha256": "a" * 64},
    {"bytes": 200000, "sha256": "a" * 64},
    {"bytes": 5, "sha256": "INVALID"},
    {"bytes": "12", "sha256": "a" * 64},
    {},
])
def test_restore_rejects_malformed_manifest_metadata(tmp_path, metadata):
    settings, holdings, agenda = fixture_files(tmp_path)
    snapshot = tmp_path / "backup"
    backup(settings, snapshot)
    previous = holdings.read_bytes()
    manifest = snapshot / "manifest.json"
    payload = json.loads(manifest.read_text())
    payload["files"]["portfolio"] = metadata
    manifest.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="metadata"):
        restore(settings, snapshot, force=True)
    assert holdings.read_bytes() == previous


def test_restore_rejects_manifest_symlink(tmp_path):
    settings, holdings, agenda = fixture_files(tmp_path)
    snapshot = tmp_path / "backup"
    backup(settings, snapshot)
    manifest = snapshot / "manifest.json"
    original = snapshot / "actual.json"
    manifest.replace(original)
    manifest.symlink_to(original)
    with pytest.raises(ValueError, match="manifest"):
        restore(settings, snapshot, force=True)


def test_restore_rejects_large_manifest_without_decoding(tmp_path):
    settings, holdings, agenda = fixture_files(tmp_path)
    snapshot = tmp_path / "backup"
    backup(settings, snapshot)
    manifest = snapshot / "manifest.json"
    manifest.write_bytes(b" " * (16 * 1024 + 1))
    with pytest.raises(ValueError, match="manifest"):
        restore(settings, snapshot, force=True)


def test_backup_refuses_destination_created_during_staging(tmp_path, monkeypatch):
    from macos import backup as module
    settings, holdings, agenda = fixture_files(tmp_path)
    destination = tmp_path / "snapshots" / "backup-001"
    chmod = module.os.chmod
    injected = {"yes": False}
    def overlap(path, mode):
        chmod(path, mode)
        if str(path).endswith("manifest.json") and not injected["yes"]:
            injected["yes"] = True
            destination.mkdir(parents=True)
    monkeypatch.setattr(module.os, "chmod", overlap)
    with pytest.raises(FileExistsError):
        module.backup(settings, destination)
    assert destination.is_dir()
    assert not (destination / "manifest.json").exists()


def test_backup_copy_failure_removes_incomplete_directory(tmp_path, monkeypatch):
    from macos import backup as module
    settings, holdings, agenda = fixture_files(tmp_path)
    destination = tmp_path / "snapshots" / "backup-001"
    replace = module.os.replace
    calls = {"n": 0}
    def fail_later(src, dst):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("simulated backup disk failure")
        return replace(src, dst)
    monkeypatch.setattr(module.os, "replace", fail_later)
    with pytest.raises(OSError, match="simulated"):
        module.backup(settings, destination)
    assert not destination.exists()
    assert holdings.is_file() and agenda.is_file()
