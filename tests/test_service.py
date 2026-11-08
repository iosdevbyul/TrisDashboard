import plistlib
from pathlib import Path

from macos.service import LABEL, PORT, agent_path, service_config


def test_default_service_only_accepts_localhost(tmp_path: Path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    config = service_config(project, home)
    assert config["Label"] == LABEL
    assert config["ProgramArguments"][-2:] == ["--port", str(PORT)]
    assert config["ProgramArguments"][4:6] == ["--host", "127.0.0.1"]
    assert config["WorkingDirectory"] == str(project)
    assert config["RunAtLoad"] is True
    assert config["KeepAlive"] == {"SuccessfulExit": False}
    assert plistlib.loads(plistlib.dumps(config)) == config


def test_lan_service_requires_explicit_opt_in(tmp_path: Path):
    config = service_config(tmp_path / "project", tmp_path / "home", lan=True)
    assert config["ProgramArguments"][4:6] == ["--host", "0.0.0.0"]


def test_agent_is_installed_for_current_user(tmp_path: Path):
    path = agent_path(tmp_path)
    assert path == tmp_path / "Library" / "LaunchAgents" / (LABEL + ".plist")


def test_public_settings_for_launchd(tmp_path: Path):
    import json
    from macos.service import read_public_settings
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "TRIS_LATITUDE": 37.5,
        "TRIS_LONGITUDE": 127.0,
        "TRIS_LOCATION_NAME": "Seoul",
        "TRIS_GITHUB_REPOS": "iosdevbyul/TrisDashboard"
    }))
    settings = read_public_settings(path)
    config = service_config(tmp_path / "project", tmp_path / "home", lan=True, settings=settings)
    assert config["EnvironmentVariables"]["TRIS_LATITUDE"] == "37.5"
    assert plistlib.loads(plistlib.dumps(config)) == config


def test_secrets_not_allowed_in_launchd_settings(tmp_path: Path):
    import pytest
    from macos.service import read_public_settings
    path = tmp_path / "settings.json"
    path.write_text('{"GITHUB_TOKEN": "secret"}')
    with pytest.raises(ValueError, match="Unsupported"):
        read_public_settings(path)


def test_portfolio_path_is_allowed_but_must_be_absolute(tmp_path: Path):
    import json
    import pytest
    from macos.service import read_public_settings
    file = tmp_path / "settings.json"
    file.write_text(json.dumps({"TRIS_PORTFOLIO_FILE": str(tmp_path / "private.json")}))
    settings = read_public_settings(file)
    assert settings["TRIS_PORTFOLIO_FILE"].endswith("private.json")
    file.write_text('{"TRIS_PORTFOLIO_FILE": "private.json"}')
    with pytest.raises(ValueError, match="absolute JSON path"):
        read_public_settings(file)


def test_coordinates_reject_non_finite_values(tmp_path):
    import json
    import pytest
    from macos.service import read_public_settings
    file = tmp_path / "settings.json"
    for invalid in ("NaN", "Infinity", "-Infinity", "1e9999"):
        file.write_text(json.dumps({"TRIS_LATITUDE": invalid}))
        with pytest.raises(ValueError, match="Invalid coordinate"):
            read_public_settings(file)
    file.write_text(json.dumps({"TRIS_LATITUDE": 37.56, "TRIS_LONGITUDE": 126.97}))
    assert read_public_settings(file)["TRIS_LATITUDE"] == "37.56"


def test_private_files_are_rejected_inside_repository(tmp_path):
    import json
    import pytest
    from macos.service import read_public_settings
    project = Path(__file__).resolve().parent.parent
    settings = tmp_path / "settings.json"
    for key in ("TRIS_PORTFOLIO_FILE", "TRIS_FITNESS_FILE",
                "TRIS_DIVIDENDS_FILE", "TRIS_AGENDA_FILE"):
        settings.write_text(json.dumps({key: str(project / "private-data.json")}))
        with pytest.raises(ValueError, match="outside the repository"):
            read_public_settings(settings)


def test_private_file_symlink_into_repo_is_rejected(tmp_path):
    import json
    import pytest
    from macos.service import read_public_settings
    project = Path(__file__).resolve().parent.parent
    alias = tmp_path / "private.json"
    alias.symlink_to(project / "frontend" / "private.json")
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"TRIS_FITNESS_FILE": str(alias)}))
    with pytest.raises(ValueError, match="outside the repository"):
        read_public_settings(settings)


def test_private_file_outside_repo_remains_valid(tmp_path):
    import json
    from macos.service import read_public_settings
    path = tmp_path / "portfolio.json"
    config = tmp_path / "settings.json"
    config.write_text(json.dumps({"TRIS_PORTFOLIO_FILE": str(path)}))
    assert read_public_settings(config)["TRIS_PORTFOLIO_FILE"] == str(path)


def test_duplicate_settings_keys_rejected(tmp_path):
    from macos.service import read_public_settings
    import pytest
    file = tmp_path / "settings.json"
    file.write_text('{"TRIS_LOCATION_NAME":"Seoul","TRIS_LOCATION_NAME":"Busan"}')
    with pytest.raises(ValueError, match="Duplicate settings key"):
        read_public_settings(file)


def test_json_non_finite_literals_rejected_before_launch(tmp_path):
    from macos.service import read_public_settings
    import pytest
    file = tmp_path / "settings.json"
    for invalid in ("NaN", "Infinity", "-Infinity"):
        file.write_text('{"TRIS_LATITUDE":' + invalid + '}')
        with pytest.raises(ValueError, match="Non-finite settings value"):
            read_public_settings(file)


def test_normal_json_configuration_still_parses(tmp_path):
    from macos.service import read_public_settings
    file = tmp_path / "settings.json"
    file.write_text('{"TRIS_LOCATION_NAME":"Seoul","TRIS_LATITUDE":37.5}')
    assert read_public_settings(file)["TRIS_LATITUDE"] == "37.5"
