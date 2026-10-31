"""Mandatory verification choke for A3 marketplace-first package execution.

Every public install/execute path in client.py must call verify_package
before execute_package_content. Fail closed. HMAC-SHA256 is the owner
binding under single-owner PR-ONLY; a missing or stripped MAC is the
signature-stripped class.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import unicodedata
from typing import Any

CHOKE_NAME = "verify_package"
ID_RE = re.compile(r"^[a-z][a-z0-9._-]*$")
OWNER_MAC_KEY = b"arc-0020-owner-mac-fixture-key-not-an-api-secret"
REFUSE_METADATA = "metadata-validation-failed"
REFUSE_TYPOSQUAT = "package-id-not-exact-lockfile-match"
REFUSE_HOMOGLYPH = "package-id-nfkc-not-identity"
REFUSE_PUBLIC_FALLBACK = "public-registry-fallback-forbidden"
REFUSE_WRONG_SOURCE = "source-registry-not-private-index"
REFUSE_OVER_PERMISSION = "permissions-not-subset-of-allowlist"
REFUSE_STALE_CRL = "crl-stale-fail-closed"
REFUSE_REVOKED = "package-revoked"
REFUSE_SIGNATURE = "signature-verification-failed"


def content_bytes(package: dict[str, Any]) -> bytes:
    raw = package.get("content_bytes")
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    return str(package.get("content") or "").encode("utf-8")


def canonical_message(package: dict[str, Any]) -> bytes:
    body = {
        "content_sha256": hashlib.sha256(content_bytes(package)).hexdigest(),
        "id": package.get("id"),
        "permissions": sorted(list(package.get("permissions") or [])),
        "source_registry": package.get("source_registry"),
        "version": package.get("version"),
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_package(package: dict[str, Any], key: bytes = OWNER_MAC_KEY) -> dict[str, Any]:
    out = dict(package)
    mac = hmac.new(key, canonical_message(out), hashlib.sha256).hexdigest()
    out["signature"] = f"hmac-sha256:{mac}"
    return out


def _refuse(reason: str, step: str) -> dict[str, Any]:
    return {"allow": False, "reason": reason, "choke": CHOKE_NAME, "step": step}


def verify_package(
    package: dict[str, Any],
    lockfile: dict[str, Any],
    *,
    now: int,
    key: bytes = OWNER_MAC_KEY,
) -> dict[str, Any]:
    """CHOKE: refuse unless metadata, identity, source, permissions, CRL, and MAC all pass."""
    pid = package.get("id")
    ver = package.get("version")
    src = package.get("source_registry")
    perms = package.get("permissions")
    if not isinstance(pid, str) or not ID_RE.match(pid):
        return _refuse(REFUSE_METADATA, "metadata")
    if not isinstance(ver, str) or not ver.strip():
        return _refuse(REFUSE_METADATA, "metadata")
    if not isinstance(src, str) or not src.strip():
        return _refuse(REFUSE_METADATA, "metadata")
    if not isinstance(perms, list) or not all(isinstance(p, str) for p in perms):
        return _refuse(REFUSE_METADATA, "metadata")
    if unicodedata.normalize("NFKC", pid) != pid:
        return _refuse(REFUSE_HOMOGLYPH, "identity")

    pinned = (lockfile.get("packages") or {}).get(pid)
    if not isinstance(pinned, dict) or pinned.get("id") != pid:
        return _refuse(REFUSE_TYPOSQUAT, "identity")
    if pinned.get("version") != ver:
        return _refuse(REFUSE_TYPOSQUAT, "identity")

    if lockfile.get("allow_public_fallback") is True:
        return _refuse(REFUSE_PUBLIC_FALLBACK, "source")
    if src != lockfile.get("registry_id") or src != pinned.get("source_registry"):
        return _refuse(REFUSE_WRONG_SOURCE, "source")

    allowlist = set(lockfile.get("allowlist_permissions") or [])
    if not set(perms).issubset(allowlist):
        return _refuse(REFUSE_OVER_PERMISSION, "permissions")

    try:
        fetched = int(lockfile.get("crl_fetched_at"))
        max_age = int(lockfile.get("crl_max_age_s"))
    except (TypeError, ValueError):
        return _refuse(REFUSE_STALE_CRL, "revocation")
    if now - fetched > max_age:
        return _refuse(REFUSE_STALE_CRL, "revocation")
    revoked = lockfile.get("revoked") or {}
    if pid in revoked:
        return _refuse(REFUSE_REVOKED, "revocation")

    sig = package.get("signature")
    if not isinstance(sig, str) or not sig.startswith("hmac-sha256:"):
        return _refuse(REFUSE_SIGNATURE, "signature")
    expected = sign_package(package, key).get("signature")
    if not isinstance(expected, str) or not hmac.compare_digest(sig, expected):
        return _refuse(REFUSE_SIGNATURE, "signature")
    return {"allow": True, "reason": "ok", "choke": CHOKE_NAME, "step": "allow"}
