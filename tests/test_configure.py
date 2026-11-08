import json
import stat
import pytest
from macos.configure import create_settings
from macos.service import read_public_settings


def test_creates_private_non_secret_settings(tmp_path):
    output = tmp_path / "settings.json"
    fitness = tmp_path / "workout-history.json"
    status = create_settings(output, fitness=fitness)
    data = read_public_settings(output)
    assert status["created"]
    assert data["TRIS_FITNESS_FILE"] == str(fitness)
    assert "TRIS_GITHUB_TOKEN" not in data
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    with pytest.raises(ValueError, match="already exists"):
        create_settings(output)


def test_settings_are_never_clobbered(tmp_path):
    output = tmp_path / "settings.json"
    output.write_text('{"owner":"keep"}')
    before = output.read_bytes()
    with pytest.raises(ValueError):
        create_settings(output)
    assert output.read_bytes() == before


def test_rejects_repository_destination():
    from pathlib import Path
    project = Path(__file__).resolve().parent.parent
    with pytest.raises(ValueError, match="outside"):
        create_settings(project / "local-settings.json")


def test_no_implicit_private_file_creation(tmp_path):
    output = tmp_path / "settings.json"
    fitness = tmp_path / "private-fitness.json"
    create_settings(output, fitness=fitness)
    assert output.exists()
    assert not fitness.exists()
