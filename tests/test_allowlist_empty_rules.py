import pytest
from backend.access import allowed_client


@pytest.mark.parametrize("policy", [
    "127.0.0.1,",
    ",127.0.0.1",
    "127.0.0.1,,192.168.1.0/24",
    "127.0.0.1,   ",
])
def test_empty_allowlist_entries_never_grant_access(policy):
    assert allowed_client("127.0.0.1", policy) is False


def test_valid_allowlist_still_grants_access():
    assert allowed_client("127.0.0.1", "127.0.0.1,192.168.1.0/24")
