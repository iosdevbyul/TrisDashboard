import os
from macos.secure_launch import SERVICE_NAMES, provider_environment, keychain_value
from macos.service import service_config


def test_keychain_values_in_process_only():
    def lookup(service):
        return "secret-" + service
    original = {"TRIS_LOCATION_NAME": "Seoul"}
    result = provider_environment(original, lookup=lookup)
    assert result["TRIS_LOCATION_NAME"] == "Seoul"
    assert set(SERVICE_NAMES).issubset(result)
    assert original == {"TRIS_LOCATION_NAME": "Seoul"}


def test_missing_keychain_item_keeps_explicit_environment():
    env = {"TRIS_GITHUB_TOKEN": "provided"}
    assert provider_environment(env, lookup=lambda _: None)["TRIS_GITHUB_TOKEN"] == "provided"


def test_keychain_command_does_not_embed_secret_in_args():
    commands = []
    def runner(argv, **kwargs):
        commands.append(argv)
        return type("Completed", (), {"returncode": 0, "stdout": "from-keychain\n"})()
    assert keychain_value("ai.tris.dashboard.github", runner=runner) == "from-keychain"
    assert commands[0][-1] == "-w"
    assert "from-keychain" not in repr(commands)


def test_launchd_uses_wrapper_without_secret_settings(tmp_path):
    config = service_config(tmp_path, tmp_path, lan=True,
                            settings={"TRIS_GITHUB_REPOS": "owner/repo"}, keychain=True)
    args = config["ProgramArguments"]
    assert args[1:3] == ["-m", "macos.secure_launch"]
    assert args[-4:] == ["--host", "0.0.0.0", "--port", "8080"]
    assert "TOKEN" not in str(config)


def test_credential_status_never_discloses_values():
    from macos.secure_launch import credential_status
    values = credential_status(lookup=lambda service: "sensitive-" + service)
    assert all(values.values())
    assert "sensitive" not in str(values)


def test_credential_status_reports_missing_item_and_missing_security_binary():
    from macos.secure_launch import credential_status
    def missing(service):
        if service.endswith("github"):
            raise OSError("security command unavailable")
        return None
    values = credential_status(lookup=missing)
    assert all(value is False for value in values.values())


def test_keychain_lookup_error_does_not_block_public_dashboard():
    from macos.secure_launch import provider_environment
    def missing(service):
        raise OSError("security unavailable")
    values = provider_environment({"TRIS_GITHUB_REPOS": "owner/public"}, lookup=missing)
    assert values == {"TRIS_GITHUB_REPOS": "owner/public"}
