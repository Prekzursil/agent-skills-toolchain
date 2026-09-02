"""HMAC-SHA256 detached signatures for marketplace fixture packages.

A signature record is a JSON object of four strings::

    {"algorithm": "hmac-sha256",
     "digest":    "<sha256 hex of the canonical payload bytes>",
     "key_id":    "<publisher key id>",
     "signature": "<hmac-sha256 hex over the canonical payload bytes>"}

The MAC key is the publisher secret looked up by ``key_id`` in a key store
(``key_id -> secret bytes``).  ``verify_signature`` is fail-closed: it returns a
status string and only ``"OK"`` means the record is authentic for the payload.
A missing record is ``"UNSIGNED"`` -- a distinct status, never a pass -- so an
install gate can refuse unsigned packages while a linter can name the gap.

The bundled key store holds exactly one key: the IMP-0118 fixture publisher.
Its secret is a *documented non-credential*: it signs only the synthetic fixture
registry under ``tools/marketplace/fixture/`` and protects nothing else, which is
why it may live in the repository (IMP-0118 receipt, ``secret_class``).
Production publishers use ed25519 via :mod:`marketplace.signature` instead.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Mapping

ALGORITHM = "hmac-sha256"

OK = "OK"
UNSIGNED = "UNSIGNED"
MALFORMED = "MALFORMED"
UNSUPPORTED_ALGORITHM = "UNSUPPORTED_ALGORITHM"
UNKNOWN_KEY = "UNKNOWN_KEY"
DIGEST_MISMATCH = "DIGEST_MISMATCH"
BAD_SIGNATURE = "BAD_SIGNATURE"
STATUSES = (OK, UNSIGNED, MALFORMED, UNSUPPORTED_ALGORITHM, UNKNOWN_KEY, DIGEST_MISMATCH, BAD_SIGNATURE)

RECORD_FIELDS = ("algorithm", "digest", "key_id", "signature")

FIXTURE_KEY_ID = "imp-0118-fixture-publisher"
# Documented non-credential: authenticates only the synthetic IMP-0118 fixture registry.
FIXTURE_SECRET = b"imp-0118-fixture-publisher/documented-non-credential/hmac-sha256"
FIXTURE_KEYS: Mapping[str, bytes] = {FIXTURE_KEY_ID: FIXTURE_SECRET}

_HEX_CHARS = frozenset("0123456789abcdef")


@dataclass(frozen=True)
class VerifyResult:
    """Outcome of a verification: ``status`` is one of :data:`STATUSES`."""

    status: str
    reason: str
    key_id: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == OK


def canonical_bytes(payload: Any) -> bytes:
    """Return the bytes that are digested and MAC'd for ``payload``.

    ``bytes`` are taken as-is except that CRLF is folded to LF (matching
    :func:`marketplace.storage.digest_bytes`, so a record's ``digest`` equals the
    registry's stored blob digest); ``str`` is UTF-8 encoded then folded the same
    way; any other JSON-serialisable value is encoded as compact, key-sorted,
    ASCII JSON so ``{"a": 1, "b": 2}`` and ``{"b": 2, "a": 1}`` sign identically.
    """
    if isinstance(payload, (bytes, bytearray, memoryview)):
        return bytes(payload).replace(b"\r\n", b"\n")
    if isinstance(payload, str):
        return payload.encode("utf-8").replace(b"\r\n", b"\n")
    try:
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"payload is not signable: {type(payload).__name__}") from exc
    return text.encode("ascii")


def payload_digest(payload: Any) -> str:
    """Lower-case SHA-256 hex of :func:`canonical_bytes`."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _mac_hex(secret: bytes, canonical: bytes) -> str:
    return hmac.new(bytes(secret), canonical, hashlib.sha256).hexdigest()


def _normalise_algorithm(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def _is_hex(value: str) -> bool:
    return bool(value) and len(value) % 2 == 0 and set(value) <= _HEX_CHARS


def sign_payload(
    payload: Any,
    *,
    key_id: str = FIXTURE_KEY_ID,
    keys: Mapping[str, bytes] | None = None,
) -> dict[str, str]:
    """Produce a signature record for ``payload`` under ``key_id``.

    Raises ``KeyError`` when ``key_id`` is not in the key store.
    """
    store = FIXTURE_KEYS if keys is None else keys
    if key_id not in store:
        raise KeyError(f"unknown signing key id {key_id!r}")
    canonical = canonical_bytes(payload)
    return {
        "algorithm": ALGORITHM,
        "digest": hashlib.sha256(canonical).hexdigest(),
        "key_id": str(key_id),
        "signature": _mac_hex(store[key_id], canonical),
    }


def verify_detailed(
    payload: Any,
    record: Mapping[str, Any] | None,
    keys: Mapping[str, bytes] | None = None,
) -> VerifyResult:
    """Verify ``record`` against ``payload`` and explain the outcome.

    Checks run in a fixed order and stop at the first failure: presence, shape,
    algorithm, key id, digest, then the MAC (compared in constant time).  Only the
    payload's canonicalisation may raise (``TypeError`` for unsignable values);
    every defect in the record maps to a status.
    """
    if record is None:
        return VerifyResult(UNSIGNED, "no signature record")
    if not isinstance(record, Mapping):
        return VerifyResult(MALFORMED, f"record is {type(record).__name__}, not an object")
    fields: dict[str, str] = {}
    for name in RECORD_FIELDS:
        value = record.get(name)
        if not isinstance(value, str) or not value.strip():
            return VerifyResult(MALFORMED, f"record field {name!r} missing or not a non-empty string")
        fields[name] = value.strip()
    if _normalise_algorithm(fields["algorithm"]) != ALGORITHM:
        return VerifyResult(
            UNSUPPORTED_ALGORITHM, f"algorithm {fields['algorithm']!r} is not {ALGORITHM}"
        )
    key_id = fields["key_id"]
    store = FIXTURE_KEYS if keys is None else keys
    if key_id not in store:
        return VerifyResult(UNKNOWN_KEY, f"key id {key_id!r} is not in the key store", key_id)
    claimed_digest = fields["digest"].lower()
    claimed_mac = fields["signature"].lower()
    if not _is_hex(claimed_digest) or not _is_hex(claimed_mac):
        return VerifyResult(MALFORMED, "digest and signature must be hex strings", key_id)
    canonical = canonical_bytes(payload)
    actual_digest = hashlib.sha256(canonical).hexdigest()
    if not hmac.compare_digest(claimed_digest, actual_digest):
        return VerifyResult(
            DIGEST_MISMATCH, f"record digest {claimed_digest[:16]}.. != payload {actual_digest[:16]}..", key_id
        )
    if not hmac.compare_digest(claimed_mac, _mac_hex(store[key_id], canonical)):
        return VerifyResult(BAD_SIGNATURE, "HMAC does not verify under the named key", key_id)
    return VerifyResult(OK, "signature verifies", key_id)


def verify_signature(
    payload: Any,
    record: Mapping[str, Any] | None,
    keys: Mapping[str, bytes] | None = None,
) -> str:
    """Return the verification status string for ``record`` over ``payload``.

    ``"OK"`` is the only passing status; ``None`` yields ``"UNSIGNED"``; every
    other defect yields one of the failure statuses in :data:`STATUSES`.
    """
    return verify_detailed(payload, record, keys).status


def encode_record(record: Mapping[str, Any]) -> bytes:
    """Canonical wire form of a record: compact, key-sorted, ASCII JSON."""
    obj = {name: str(record[name]) for name in RECORD_FIELDS}
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def decode_record(wire: bytes | str) -> dict[str, str]:
    """Parse a wire record strictly.

    Rejects duplicate keys, non-object documents, missing or extra fields and
    non-string values with ``ValueError``.
    """
    text = wire.decode("utf-8") if isinstance(wire, (bytes, bytearray)) else str(wire)

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        keys = [k for k, _ in pairs]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate keys in signature record")
        return dict(pairs)

    try:
        obj = json.loads(text, object_pairs_hook=no_duplicates)
    except json.JSONDecodeError as exc:
        raise ValueError(f"signature record is not valid JSON: {exc.msg}") from exc
    if not isinstance(obj, dict):
        raise ValueError("signature record must be a JSON object")
    if set(obj) != set(RECORD_FIELDS):
        raise ValueError(f"signature record fields must be exactly {sorted(RECORD_FIELDS)}")
    if not all(isinstance(v, str) for v in obj.values()):
        raise ValueError("signature record values must be strings")
    return {name: obj[name] for name in RECORD_FIELDS}


__all__ = [
    "ALGORITHM",
    "BAD_SIGNATURE",
    "DIGEST_MISMATCH",
    "FIXTURE_KEYS",
    "FIXTURE_KEY_ID",
    "FIXTURE_SECRET",
    "MALFORMED",
    "OK",
    "RECORD_FIELDS",
    "STATUSES",
    "UNKNOWN_KEY",
    "UNSIGNED",
    "UNSUPPORTED_ALGORITHM",
    "VerifyResult",
    "canonical_bytes",
    "decode_record",
    "encode_record",
    "payload_digest",
    "sign_payload",
    "verify_detailed",
    "verify_signature",
]
