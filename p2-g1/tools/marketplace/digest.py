"""Canonical sha256 (LF-normalized)."""
from __future__ import annotations


def sha256_hex(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
