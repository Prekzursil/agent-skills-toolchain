"""Owner-side signing helpers for tests (IMP-0079 fixtures).

Two deterministic Ed25519 key pairs are derived from fixed seeds: the
marketplace *owner* key (trusted - :func:`owner_public_map` publishes only its
public half) and an *untrusted* key (a perfectly valid Ed25519 key that is
simply not the owner, for the forged-list probes).  :func:`sign_list` wraps a
``marketplace.revocation-list/v1`` body in the signed envelope the client
verifies; :func:`dumps_list` renders any document as the canonical bytes a
transport serves.  No random key generation, no wall clock: signed fixtures are
reproducible, and the private halves never leave this module except through
:func:`private_key_for` (test code only).
"""
from __future__ import annotations

import hashlib
from typing import Any, Mapping

from ..revocation import canonical_json, load_private_key, sign_envelope

try:
    from cryptography.hazmat.primitives import serialization
except ImportError:  # pragma: no cover - only where cryptography is absent
    serialization = None  # type: ignore[assignment]

__all__ = [
    "OWNER_KEY_ID",
    "SIGNERS",
    "UNTRUSTED_KEY_ID",
    "dumps_list",
    "owner_public_map",
    "private_key_for",
    "public_key_hex",
    "seed_for",
    "sign_list",
    "tampered_list",
]

OWNER_KEY_ID = "marketplace-owner"
UNTRUSTED_KEY_ID = "not-the-owner"

#: Named test signers -> the key id each one claims in its signature object.
SIGNERS: dict[str, str] = {"owner": OWNER_KEY_ID, "untrusted": UNTRUSTED_KEY_ID}

_SEED_DOMAIN = b"ast-integrate/marketplace/revocation-list/fixtures/v1:"


def _signer(name: str) -> str:
    if name not in SIGNERS:
        raise KeyError(f"unknown test signer {name!r}; choose one of {sorted(SIGNERS)}")
    return name


def seed_for(signer: str = "owner") -> bytes:
    """The fixed 32-byte Ed25519 seed of a named test signer (domain-separated SHA-256)."""
    return hashlib.sha256(_SEED_DOMAIN + _signer(signer).encode("ascii")).digest()


def private_key_for(signer: str = "owner"):
    """The ``Ed25519PrivateKey`` of a named test signer (deterministic)."""
    return load_private_key(seed_for(signer))


def public_key_hex(signer: str = "owner") -> str:
    """Hex of the 32 raw public-key bytes of a named test signer."""
    public = private_key_for(signer).public_key()
    raw_getter = getattr(public, "public_bytes_raw", None)
    if callable(raw_getter):
        return raw_getter().hex()
    if serialization is None:  # pragma: no cover
        raise RuntimeError("the 'cryptography' package is required for the signing fixtures")
    return public.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()


def owner_public_map() -> dict[str, str]:
    """What a client trusts: ``{OWNER_KEY_ID: <hex public key>}``.

    The untrusted signer is deliberately absent, so a list it signs is rejected
    as "signed only by untrusted key(s)" rather than accepted.
    """
    return {OWNER_KEY_ID: public_key_hex("owner")}


def sign_list(
    body: Mapping[str, Any],
    *,
    signer: str = "owner",
    key_id: str | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Sign ``body`` as ``signer`` and return the ``marketplace.revocation-list-envelope/v1``.

    ``key_id`` overrides the key id *claimed* in the signature object - signing
    with the untrusted key while claiming ``OWNER_KEY_ID`` builds the tamper
    case where a trusted key's signature does not verify.  ``validate=False``
    lets a test sign a deliberately malformed body.
    """
    name = _signer(signer)
    claimed = SIGNERS[name] if key_id is None else key_id
    return sign_envelope(body, key_id=claimed, private_key=private_key_for(name), validate=validate)


def tampered_list(envelope: Mapping[str, Any], **body_changes: Any) -> dict[str, Any]:
    """Copy ``envelope`` with ``body_changes`` applied and the original signature kept.

    The result is a real signed document whose signature no longer matches its
    body - the client must reject it.
    """
    if not isinstance(envelope, Mapping) or not isinstance(envelope.get("body"), Mapping):
        raise TypeError("tampered_list expects a signed envelope with a 'body' object")
    if not body_changes:
        raise ValueError("tampered_list needs at least one body change")
    doc = dict(envelope)
    body = dict(envelope["body"])
    body.update(body_changes)
    doc["body"] = body
    return doc


def dumps_list(doc: Mapping[str, Any]) -> bytes:
    """Canonical JSON bytes of ``doc`` (signed envelope or bare body) as a transport serves them."""
    if not isinstance(doc, Mapping):
        raise TypeError(f"dumps_list expects a mapping, not {type(doc).__name__}")
    return canonical_json(dict(doc))
