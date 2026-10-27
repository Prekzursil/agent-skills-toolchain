"""Synthetic signatures for offline-bundle tests. Not production crypto."""
from __future__ import annotations

import hashlib
import hmac


def private_pem(label: str = "imp0108") -> bytes:
    body = f"SYNTHETIC-NOT-A-REAL-KEY-BODY-{label.upper()}".encode("utf-8")
    return b"-----BEGIN PRIVATE KEY-----\n" + body + b"\n-----END PRIVATE KEY-----\n"


def verify_signature(payload: bytes, signature: bytes, public_key: bytes | None = None) -> bool:
    digest = hmac.new(b"imp0108-test-key", payload, hashlib.sha256).digest()
    return hmac.compare_digest(digest, signature) if signature else False


def sign_bytes(payload: bytes, key: bytes | None = None) -> bytes:
    material = key or b"imp0108-test-key"
    return hmac.new(material, payload, hashlib.sha256).digest()
