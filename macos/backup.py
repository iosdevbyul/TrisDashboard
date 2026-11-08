"""Offline backup/restore of explicitly configured private dashboard JSON files."""
import argparse
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

from macos.preflight import FILE_LOADERS
from macos.service import read_public_settings

MANIFEST = "manifest.json"
MAX_FILE_BYTES = 128 * 1024
MAX_MANIFEST_BYTES = 16 * 1024


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def configured_files(settings_file: Path) -> dict[str, tuple[Path, object]]:
    settings = read_public_settings(settings_file)
    results = {}
    for label, (env_name, loader) in FILE_LOADERS.items():
        if env_name in settings:
            results[label] = (Path(settings[env_name]).expanduser().resolve(), loader)
    return results


def backup(settings_file: Path, destination: Path) -> dict:
    source = configured_files(settings_file)
    destination = destination.expanduser().resolve()
    project = Path(__file__).resolve().parent.parent
    if project == destination or project in destination.parents:
        raise ValueError("Backups must live outside the public repository")
    if destination.exists():
        raise ValueError("Backup directory already exists")
    if not source:
        raise ValueError("No private data files configured")
    # Validate and stage all originals before creating the final backup directory.
    originals = {}
    for name, (path, loader) in source.items():
        loader(path)
        data = path.read_bytes()
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("Source file too large")
        originals[name] = data
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".tris-backup-", dir=destination.parent))
    os.chmod(temp, 0o700)
    try:
        manifest = {"version": 1, "created_utc": datetime.now(timezone.utc).isoformat(), "files": {}}
        for name, data in originals.items():
            filename = name + ".json"
            path = temp / filename
            path.write_bytes(data)
            os.chmod(path, 0o600)
            manifest["files"][name] = {"sha256": digest(data), "bytes": len(data)}
        manifest_file = temp / MANIFEST
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        os.chmod(manifest_file, 0o600)
        # Reserve the final directory name exclusively: POSIX rename can
        # overwrite an empty directory that appeared after our earlier check.
        destination.mkdir(mode=0o700, exist_ok=False)
        owned = destination.lstat()
        try:
            # Publish the checksum manifest last so incomplete backups never
            # pass validation, even if a process exits unexpectedly.
            for name in originals:
                filename = name + ".json"
                os.replace(temp / filename, destination / filename)
            os.replace(manifest_file, destination / MANIFEST)
        except Exception:
            try:
                current = destination.lstat()
                if (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino):
                    shutil.rmtree(destination)
            except FileNotFoundError:
                pass
            raise
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return {"backed_up": len(originals), "created": True}


def _unique_manifest_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate backup manifest key")
        result[key] = value
    return result


def _reject_manifest_constant(value):
    raise ValueError("Non-standard backup manifest constant")


def validate_backup(directory: Path) -> dict:
    directory = directory.expanduser()
    if directory.is_symlink():
        raise ValueError("Backup directory must not be a symlink")
    directory = directory.resolve()
    manifest_path = directory / MANIFEST
    if (manifest_path.is_symlink() or not manifest_path.is_file()
            or manifest_path.stat().st_size > MAX_MANIFEST_BYTES):
        raise ValueError("Invalid backup manifest file")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_manifest_keys,
                          parse_constant=_reject_manifest_constant)
    if not isinstance(manifest, dict) or type(manifest.get("version")) is not int or manifest["version"] != 1:
        raise ValueError("Unsupported backup manifest")
    created_raw = manifest.get("created_utc")
    if not isinstance(created_raw, str):
        raise ValueError("Invalid backup creation time")
    try:
        created = datetime.fromisoformat(created_raw)
        if created.tzinfo is None or created.utcoffset() is None:
            raise ValueError("Missing backup creation timezone")
        if created > datetime.now(timezone.utc) + timedelta(minutes=10):
            raise ValueError("Future backup creation time")
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError("Invalid backup creation time") from error
    entries = manifest.get("files")
    if not isinstance(entries, dict) or not entries:
        raise ValueError("Backup manifest is empty")
    if any(name not in FILE_LOADERS for name in entries):
        raise ValueError("Unknown backup file")
    for name, metadata in entries.items():
        if (not isinstance(metadata, dict)
                or type(metadata.get("bytes")) is not int
                or not 0 <= metadata["bytes"] <= MAX_FILE_BYTES
                or not isinstance(metadata.get("sha256"), str)
                or len(metadata["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in metadata["sha256"])):
            raise ValueError("Invalid backup metadata")
        path = directory / (name + ".json")
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("Invalid backup file")
        with path.open("rb") as stream:
            content = stream.read(MAX_FILE_BYTES + 1)
        if (len(content) > MAX_FILE_BYTES or len(content) != metadata["bytes"]
                or digest(content) != metadata["sha256"]):
            raise ValueError("Backup data checksum mismatch")
    return entries


def restore(settings_file: Path, directory: Path, *, force: bool = False) -> dict:
    files = configured_files(settings_file)
    entries = validate_backup(directory)
    if any(name not in files for name in entries):
        raise ValueError("Configured target missing for backup content")
    directory = directory.expanduser().resolve()
    # Dry-run and actual restore both require schema validation, not just checksums.
    for name, (target, loader) in files.items():
        if name in entries:
            loader(directory / (name + ".json"))
            if force and not target.parent.is_dir():
                raise ValueError("Target directory missing")
    if not force:
        return {"validated": len(entries), "restored": 0}
    staged_files = []
    rollback_files = []
    replaced = []
    try:
        # Stage all incoming content and recovery copies before changing any target.
        for name in entries:
            target, _ = files[name]
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".tris-restore-",
                                             delete=False) as handle:
                staged = Path(handle.name)
                staged_files.append((staged, target))
                handle.write((directory / (name + ".json")).read_bytes())
            os.chmod(staged, 0o600)
            if target.exists():
                with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".tris-rollback-",
                                                 delete=False) as handle:
                    recovery = Path(handle.name)
                    handle.write(target.read_bytes())
                os.chmod(recovery, 0o600)
                rollback_files.append((target, recovery))
            else:
                rollback_files.append((target, None))
        for staged, target in staged_files:
            os.replace(staged, target)
            replaced.append(target)
    except Exception:
        # Best-effort rollback when one of the per-file replacements fails.
        # Restore old bytes with same-directory replacements; do not delete failed targets.
        recovery_map = dict(rollback_files)
        errors = []
        for target in reversed(replaced):
            recovery = recovery_map[target]
            try:
                if recovery is None:
                    target.unlink()
                else:
                    os.replace(recovery, target)
            except OSError as error:
                errors.append(error)
        if errors:
            raise RuntimeError("Restore failed and rollback was incomplete") from None
        raise
    finally:
        for staged, target in staged_files:
            staged.unlink(missing_ok=True)
        for target, recovery in rollback_files:
            if recovery is not None:
                recovery.unlink(missing_ok=True)
    return {"validated": len(entries), "restored": len(entries)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Private offline dashboard JSON backup and restore")
    parser.add_argument("command", choices=("backup", "restore"))
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--force", action="store_true", help="Explicitly restore over configured files")
    args = parser.parse_args()
    try:
        if args.command == "backup":
            if args.force:
                raise ValueError("--force is only for restore")
            result = backup(args.settings, args.directory)
        else:
            result = restore(args.settings, args.directory, force=args.force)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, json.JSONDecodeError):
        parser.exit(1, "Backup operation failed. Check files, permissions, and checksums.\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
