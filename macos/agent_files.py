"""Write new per-user launchd plists with no accidental other-user access."""
import os
import plistlib
from pathlib import Path


def write_private_agent(path: Path, config: dict) -> tuple[int, int, int]:
    """Create once, refuse symlink targets and restrict settings paths to the owner."""
    payload = plistlib.dumps(config)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    original = os.fstat(fd)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(payload)
        os.chmod(path, 0o600)
        identity = path.lstat()
        return (identity.st_dev, identity.st_ino, identity.st_ctime_ns)
    except BaseException:
        # A replacement may have appeared after creation. Never delete it.
        try:
            current = path.lstat()
            if (not path.is_symlink() and (current.st_dev, current.st_ino)
                    == (original.st_dev, original.st_ino)):
                path.unlink()
        except FileNotFoundError:
            pass
        raise


def remove_failed_agent(path: Path, identity: tuple[int, int]) -> bool:
    """Only clean up the file created by this install attempt, not a replacement."""
    try:
        stat = path.lstat()
        if (stat.st_dev, stat.st_ino, stat.st_ctime_ns) != identity or path.is_symlink():
            return False
        path.unlink()
        return True
    except FileNotFoundError:
        return False
