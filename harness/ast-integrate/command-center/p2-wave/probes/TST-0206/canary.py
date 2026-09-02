"""Synthetic canary for TST-0206. Not a credential. Never print or persist the body.

Receipts and probe stdout may name PREFIX and the sha256 of the full token only.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

PREFIX = "SYNTHETIC_NOT_A_CREDENTIAL_TST0206_"
ENV_KEYS = ("TST0206_CANARY", "TST0206_API_SECRET")
SUFFIX_BYTES = 32


@dataclass(frozen=True)
class Canary:
    prefix: str
    suffix_len: int
    full_len: int
    sha256: str
    full: str


def mint() -> Canary:
    suffix = secrets.token_urlsafe(SUFFIX_BYTES)
    full = PREFIX + suffix
    return Canary(
        prefix=PREFIX,
        suffix_len=len(suffix),
        full_len=len(full),
        sha256=hashlib.sha256(full.encode("ascii")).hexdigest(),
        full=full,
    )


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blob_contains(blob: bytes | str, token: str) -> bool:
    needle = token.encode("ascii")
    if isinstance(blob, bytes):
        return needle in blob
    return token in blob
