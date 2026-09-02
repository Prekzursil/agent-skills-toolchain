"""Synthetic signed-package fixtures and naive mutants for TST-0220.

Keys are generated in-process for this unit only. Callers must not print
key material. Production verification is marketplace.sign.verify_package.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from marketplace.sign import (  # noqa: E402
    key_id_of,
    sign_bytes,
    trust_store_from_keys,
    verify_bytes,
    verify_package,
)

PAYLOAD = b"TST-0220 fixture package v1\n" + bytes(range(64))

EXPECTED = {
    "valid_twin": {"accepted": True, "reason": "ok"},
    "unsigned": {"accepted": False, "reason": "unsigned"},
    "untrusted_key": {"accepted": False, "reason": "untrusted-key"},
    "content_tampered": {"accepted": False, "reason": "content-tampered"},
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_fixtures() -> dict[str, Any]:
    trusted = os.urandom(32)
    untrusted = os.urandom(32)
    while untrusted == trusted:
        untrusted = os.urandom(32)
    store = trust_store_from_keys([trusted])
    key_bag = trust_store_from_keys([trusted, untrusted])
    valid_record = sign_bytes(PAYLOAD, trusted)
    untrusted_record = sign_bytes(PAYLOAD, untrusted)
    tampered = bytearray(PAYLOAD)
    tampered[0] ^= 0xFF
    tampered_b = bytes(tampered)
    if tampered_b == PAYLOAD:
        raise RuntimeError("payload flip was a no-op")
    cases = {
        "valid_twin": {
            "payload": PAYLOAD,
            "record": valid_record,
            "expected_reason": "ok",
            "expected_accepted": True,
        },
        "unsigned": {
            "payload": PAYLOAD,
            "record": None,
            "expected_reason": "unsigned",
            "expected_accepted": False,
        },
        "untrusted_key": {
            "payload": PAYLOAD,
            "record": untrusted_record,
            "expected_reason": "untrusted-key",
            "expected_accepted": False,
        },
        "content_tampered": {
            "payload": tampered_b,
            "record": valid_record,
            "expected_reason": "content-tampered",
            "expected_accepted": False,
        },
    }
    return {
        "trusted_key": trusted,
        "untrusted_key": untrusted,
        "trusted_id": key_id_of(trusted),
        "untrusted_id": key_id_of(untrusted),
        "trust_store": store,
        "key_bag": key_bag,
        "cases": cases,
        "payload_sha256": _sha(PAYLOAD),
        "tampered_sha256": _sha(tampered_b),
    }


def honest_verdicts(fx: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, case in fx["cases"].items():
        verdict = verify_package(case["payload"], case["record"], fx["trust_store"])
        out[name] = {
            "accepted": bool(verdict["accepted"]),
            "reason": verdict["reason"],
            "detail": verdict.get("detail"),
            "payload_sha256": _sha(case["payload"]),
            "record_key_id": None
            if case["record"] is None
            else case["record"].get("key_id"),
            "record_digest": None
            if case["record"] is None
            else case["record"].get("digest"),
        }
    return out


def naive_unsigned_valid_by_absence(
    payload: bytes, record: dict[str, Any] | None, trusted_keys: dict[str, bytes]
) -> dict[str, Any]:
    if record is None or not record:
        return {"accepted": True, "reason": "ok", "detail": "valid-by-absence"}
    return verify_package(payload, record, trusted_keys)


def naive_ignore_trust(
    payload: bytes, record: dict[str, Any] | None, key_bag: dict[str, bytes]
) -> dict[str, Any]:
    if record is None or not record:
        return {"accepted": False, "reason": "unsigned"}
    kid = str(record.get("key_id") or "")
    key = key_bag.get(kid)
    if key is None:
        return {"accepted": False, "reason": "untrusted-key"}
    ok = verify_bytes(payload, record, key)
    return {"accepted": ok, "reason": "ok" if ok else "content-tampered"}


def naive_skip_payload(
    payload: bytes, record: dict[str, Any] | None, trusted_keys: dict[str, bytes]
) -> dict[str, Any]:
    del payload  # mutant never inspects live bytes
    if record is None or not record:
        return {"accepted": False, "reason": "unsigned"}
    kid = str(record.get("key_id") or "")
    if kid not in trusted_keys:
        return {"accepted": False, "reason": "untrusted-key"}
    digest = str(record.get("digest") or "")
    mac = str(record.get("mac") or "")
    if digest and mac and record.get("algorithm"):
        return {"accepted": True, "reason": "ok", "detail": "record-fields-present"}
    return {"accepted": False, "reason": "content-tampered"}


def naive_matrix(fx: dict[str, Any]) -> dict[str, Any]:
    unsigned = naive_unsigned_valid_by_absence(
        fx["cases"]["unsigned"]["payload"],
        fx["cases"]["unsigned"]["record"],
        fx["trust_store"],
    )
    untrusted = naive_ignore_trust(
        fx["cases"]["untrusted_key"]["payload"],
        fx["cases"]["untrusted_key"]["record"],
        fx["key_bag"],
    )
    tampered = naive_skip_payload(
        fx["cases"]["content_tampered"]["payload"],
        fx["cases"]["content_tampered"]["record"],
        fx["trust_store"],
    )
    valid_u = naive_unsigned_valid_by_absence(
        fx["cases"]["valid_twin"]["payload"],
        fx["cases"]["valid_twin"]["record"],
        fx["trust_store"],
    )
    return {
        "unsigned_valid_by_absence": unsigned,
        "untrusted_ignore_trust": untrusted,
        "tampered_skip_payload": tampered,
        "valid_twin_still_accepted_by_unsigned_naive": valid_u,
    }


def public_meta(fx: dict[str, Any]) -> dict[str, Any]:
    return {
        "trusted_id": fx["trusted_id"],
        "untrusted_id": fx["untrusted_id"],
        "payload_sha256": fx["payload_sha256"],
        "tampered_sha256": fx["tampered_sha256"],
        "ids_distinct": fx["trusted_id"] != fx["untrusted_id"],
        "hmac_over_payload": True,
        "canonicalisation": "raw-package-bytes",
        "algorithm": "hmac-sha256",
    }


def openssl_hmac_hex(payload: bytes, key: bytes) -> str:
    """Independent HMAC-SHA256 via OpenSSL; never print key material."""
    import subprocess

    proc = subprocess.run(
        [
            "openssl",
            "dgst",
            "-sha256",
            "-mac",
            "HMAC",
            "-macopt",
            f"hexkey:{key.hex()}",
            "-hex",
        ],
        input=payload,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")[-400:]
        raise RuntimeError(f"openssl hmac failed rc={proc.returncode} {err}")
    text = (proc.stdout or b"").decode("ascii", "replace").strip()
    token = text.split()[-1].lower()
    if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
        raise RuntimeError(f"openssl hmac unparseable: {text[-200:]!r}")
    return token


def openssl_sha256_hex(payload: bytes) -> str:
    import subprocess

    proc = subprocess.run(
        ["openssl", "dgst", "-sha256", "-hex"],
        input=payload,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")[-400:]
        raise RuntimeError(f"openssl sha256 failed rc={proc.returncode} {err}")
    text = (proc.stdout or b"").decode("ascii", "replace").strip()
    token = text.split()[-1].lower()
    if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
        raise RuntimeError(f"openssl sha256 unparseable: {text[-200:]!r}")
    return token


def independent_key_id(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()[:16]


def stdlib_hmac_hex(payload: bytes, key: bytes) -> str:
    return hmac.new(key, payload, hashlib.sha256).hexdigest()
