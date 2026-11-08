import os
import plistlib
import stat
import pytest
from macos.agent_files import write_private_agent


def test_owner_only_launchagent_creation(tmp_path):
    path = tmp_path / "agent.plist"
    write_private_agent(path, {"Label": "test.local", "ProgramArguments": ["/bin/true"]})
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert plistlib.loads(path.read_bytes())["Label"] == "test.local"


def test_existing_agent_remains_unchanged(tmp_path):
    path = tmp_path / "agent.plist"
    path.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        write_private_agent(path, {"Label": "replaced"})
    assert path.read_bytes() == b"original"


def test_symlink_launchagent_cannot_overwrite_target(tmp_path):
    target = tmp_path / "private.txt"
    target.write_bytes(b"safe")
    link = tmp_path / "agent.plist"
    link.symlink_to(target)
    with pytest.raises(FileExistsError):
        write_private_agent(link, {"Label": "should-not-write"})
    assert target.read_bytes() == b"safe"


def test_private_permissions_ignore_lax_umask(tmp_path):
    path = tmp_path / "agent.plist"
    previous = os.umask(0)
    try:
        write_private_agent(path, {"Label": "test.local"})
    finally:
        os.umask(previous)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_failed_bootstrap_removes_only_original_agent(tmp_path):
    from macos.agent_files import remove_failed_agent
    path = tmp_path / "agent.plist"
    identity = write_private_agent(path, {"Label": "owner"})
    assert remove_failed_agent(path, identity) is True
    assert not path.exists()


def test_failed_bootstrap_preserves_replaced_file(tmp_path):
    from macos.agent_files import remove_failed_agent
    path = tmp_path / "agent.plist"
    identity = write_private_agent(path, {"Label": "owner"})
    path.unlink()
    other = tmp_path / "replacement.plist"
    other.write_text("replacement")
    other.replace(path)
    assert remove_failed_agent(path, identity) is False
    assert path.read_text() == "replacement"


def test_failed_bootstrap_preserves_symlink_replacement(tmp_path):
    from macos.agent_files import remove_failed_agent
    path = tmp_path / "agent.plist"
    identity = write_private_agent(path, {"Label": "owner"})
    path.unlink()
    target = tmp_path / "private.txt"
    target.write_text("private")
    path.symlink_to(target)
    assert remove_failed_agent(path, identity) is False
    assert target.read_text() == "private"


def test_failed_agent_write_preserves_concurrent_replacement(tmp_path, monkeypatch):
    from macos import agent_files
    path = tmp_path / "agent.plist"
    original_chmod = agent_files.os.chmod
    replacement = tmp_path / "replacement.plist"
    replacement.write_text("replacement")
    def replace_during_chmod(target, mode):
        if target == path:
            replacement.replace(path)
            raise OSError("simulated write failure")
        return original_chmod(target, mode)
    monkeypatch.setattr(agent_files.os, "chmod", replace_during_chmod)
    with pytest.raises(OSError, match="simulated write failure"):
        write_private_agent(path, {"Label": "test.local"})
    assert path.read_text() == "replacement"
