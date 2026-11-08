"""Write new per-user launchd plists with no accidental other-user access."""
import os
import plistlib
from pathlib import Path


def write_private_agent(path: Path, config: dict) -> None:
    """Create once, refuse symlink targets and restrict settings paths to the owner."""
    payload = plistlib.dumps(config)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(payload)
        os.chmod(path, 0o600)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
