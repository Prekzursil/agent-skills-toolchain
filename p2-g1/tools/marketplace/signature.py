"""Detached ed25519 package-digest signatures. Strict canonical wire."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

VALID = "VALID"
INVALID = "INVALID"
UNSIGNED = "UNSIGNED"
ALG = "ed25519"


@dataclass(frozen=True)
class VerifyResult:
    status: str
    reason: str = ""
    reason_code: str = ""
    key_id: str | None = None


def package_digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def encode_record(record: Mapping[str, Any]) -> bytes:
    obj = {
        "algorithm": str(record["algorithm"]),
        "digest": str(record["digest"]),
        "key_id": str(record["key_id"]),
        "signature": str(record["signature"]),
    }
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=True).encode("ascii")


def sign_record(priv: Ed25519PrivateKey, *, digest: str, key_id: str) -> dict[str, str]:
    sig = priv.sign(digest.encode("ascii"))
    return {
        "algorithm": ALG,
        "digest": digest,
        "key_id": key_id,
        "signature": sig.hex(),
    }


def _result(status: str, *, reason: str = "", reason_code: str = "", key_id: str | None = None) -> VerifyResult:
    return VerifyResult(status=status, reason=reason, reason_code=reason_code, key_id=key_id)


def verify_signature(digest: str, record: Mapping[str, Any] | None, store: Mapping[str, str]) -> VerifyResult:
    if record is None:
        return _result(UNSIGNED, reason="unsigned package", reason_code="unsigned")
    alg = str(record.get("algorithm") or "")
    if alg != ALG:
        return _result(INVALID, reason=f"unsupported algorithm {alg}", reason_code="unsupported-algorithm")
    rec_digest = str(record.get("digest") or "")
    if rec_digest != digest:
        return _result(INVALID, reason="digest mismatch", reason_code="digest-mismatch")
    key_id = str(record.get("key_id") or "")
    if key_id not in store:
        return _result(INVALID, reason="unknown key id", reason_code="unknown-key-id")
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(str(store[key_id])))
        pub.verify(bytes.fromhex(str(record.get("signature") or "")), digest.encode("ascii"))
    except Exception:
        return _result(INVALID, reason="signature mismatch", reason_code="signature-mismatch", key_id=key_id)
    return _result(VALID, reason="ok", reason_code="ok", key_id=key_id)


def verify_wire(wire: bytes, digest: str, store: Mapping[str, str]) -> VerifyResult:
    if b"\\u" in wire:
        return _result(INVALID, reason="non-canonical unicode escape", reason_code="non-canonical")
    try:
        text = wire.decode("ascii")
    except UnicodeDecodeError:
        return _result(INVALID, reason="malformed encoding", reason_code="malformed")

    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        keys = [k for k, _ in pairs]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate")
        return dict(pairs)

    try:
        obj = json.loads(text, object_pairs_hook=hook)
    except ValueError:
        return _result(INVALID, reason="duplicate keys or malformed", reason_code="malformed")
    except json.JSONDecodeError:
        return _result(INVALID, reason="malformed json", reason_code="malformed")
    if not isinstance(obj, dict):
        return _result(INVALID, reason="not object", reason_code="malformed")
    try:
        canon = encode_record(obj)
    except Exception:
        return _result(INVALID, reason="missing fields", reason_code="malformed")
    if canon != wire:
        return _result(INVALID, reason="non-canonical encoding", reason_code="non-canonical")
    return verify_signature(digest, obj, store)
