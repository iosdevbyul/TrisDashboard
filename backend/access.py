"""Optional source-IP allowlist. Never trusts forwarded-client headers."""
import ipaddress
import os


def allowed_client(host: str | None, policy: str | None = None) -> bool:
    configured = os.environ.get("TRIS_ALLOWED_CLIENT_IPS", "") if policy is None else policy
    if not configured.strip():
        return True
    if not host:
        return False
    try:
        address = ipaddress.ip_address(host)
        if getattr(address, "ipv4_mapped", None):
            address = address.ipv4_mapped
    except ValueError:
        return False
    rules = [entry.strip() for entry in configured.split(",") if entry.strip()]
    if not rules or len(rules) > 32:
        return False
    try:
        networks = [ipaddress.ip_network(entry, strict=False) for entry in rules]
    except ValueError:
        return False
    return any(address in network for network in networks)


def validate_allowlist(value: str) -> str:
    parts = [part.strip() for part in value.split(",")]
    if not 1 <= len(parts) <= 32 or any(not part for part in parts):
        raise ValueError("Invalid client allowlist")
    for part in parts:
        ipaddress.ip_network(part, strict=False)
    return ",".join(parts)
