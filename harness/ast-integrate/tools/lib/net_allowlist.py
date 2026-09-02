"""Loopback-first remote-address allowlist (Python port of net-allowlist.mjs)."""
from __future__ import annotations

from typing import Any


def normalizeRemoteAddress(remoteAddress: Any) -> str:
    raw = str(remoteAddress or "").strip()
    if not raw:
        return ""
    if raw.startswith("::ffff:"):
        return raw[len("::ffff:") :]
    return raw


def isPrivateIpv4(address: str) -> bool:
    if "." not in address:
        return False
    parts = address.split(".")
    if len(parts) != 4:
        return False
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return False
    if any(n < 0 or n > 255 for n in nums):
        return False
    if nums[0] == 10:
        return True
    if nums[0] == 192 and nums[1] == 168:
        return True
    if nums[0] == 172 and 16 <= nums[1] <= 31:
        return True
    return False


def isAllowedRemoteAddress(
    remoteAddress: Any,
    allowPrivateNetwork: bool = False,
    **kwargs: Any,
) -> bool:
    if "allowPrivateNetwork" in kwargs:
        allowPrivateNetwork = bool(kwargs["allowPrivateNetwork"])
    a = normalizeRemoteAddress(remoteAddress)
    if not a:
        return False
    if a in {"127.0.0.1", "::1"}:
        return True
    if not allowPrivateNetwork:
        return False
    if isPrivateIpv4(a):
        return True
    return a.startswith("fc") or a.startswith("fd")


FORBIDDEN_PAYLOAD_FIELDS = frozenset(
    {
        "prompt",
        "path",
        "file_contents",
        "filecontents",
        "contents",
        "body",
    }
)


class AllowlistError(Exception):
    def __init__(self, message: str, classification: str = "config-parse-rejected") -> None:
        super().__init__(message)
        self.classification = classification


def gated_request(url: str, payload: Any = None, ctx: Any = None) -> None:
    """Default-deny egress. Callers must not treat a missing consent as allow."""
    dest = str(url or "")
    raise AllowlistError(f"egress denied for {dest}", "egress-denied")


def inspect_config_keys(doc: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(doc, dict):
        raise AllowlistError("config-not-object")
    insecure_keys = ("insecure_tls", "insecure", "tls_verify")
    if doc.get("insecure_tls") is True or doc.get("insecure") is True:
        raise AllowlistError("insecure TLS flag set", "config-parse-rejected")
    if doc.get("tls_verify") is False:
        raise AllowlistError("tls_verify=false", "config-parse-rejected")
    lowered = {str(k).lower(): v for k, v in doc.items()}
    for key in ("insecure", "insecure_tls", "allow_insecure"):
        if lowered.get(key) is True:
            raise AllowlistError(f"insecure key {key}", "config-parse-rejected")
    return doc


normalize_remote_address = normalizeRemoteAddress
is_private_ipv4 = isPrivateIpv4
is_allowed_remote_address = isAllowedRemoteAddress

__all__ = [
    "normalizeRemoteAddress",
    "isPrivateIpv4",
    "isAllowedRemoteAddress",
    "normalize_remote_address",
    "is_private_ipv4",
    "is_allowed_remote_address",
]
