from backend.access import allowed_client


def test_mapped_ipv4_network_accepts_native_and_mapped_clients():
    assert allowed_client("192.168.1.42", "::ffff:192.168.1.0/120")
    assert allowed_client("::ffff:192.168.1.42", "::ffff:192.168.1.0/120")
    assert not allowed_client("192.168.2.42", "::ffff:192.168.1.0/120")


def test_regular_ipv6_network_remains_ipv6_only():
    assert allowed_client("fd12::42", "fd12::/64")
    assert not allowed_client("192.168.1.42", "fd12::/64")
