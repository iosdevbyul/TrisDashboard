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
