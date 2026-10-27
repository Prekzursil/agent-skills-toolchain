"""EOL-normalised hashing for plugin payload identity (IMP-0035 / AUD-0011).

Binary payloads pass through unchanged. Text payloads are hashed after CRLF/CR
are folded to LF. Classification is a pair of independent signals: raw sha256
and the normalised digest.
"""
from __future__ import annotations

import hashlib
from typing import Final

IDENTICAL: Final = "IDENTICAL"
IDENTICAL_MODULO_EOL: Final = "IDENTICAL_MODULO_EOL"
CONTENT_DIVERGED: Final = "CONTENT-DIVERGED"
CONTENT_DIVERGED_ALT: Final = "CONTENT_DIVERGED"
DIVERGED: Final = CONTENT_DIVERGED


def looks_binary(data: bytes) -> bool:
    if not data:
        return False
    if b"\x00" in data[:8192]:
        return True
    sample = data[:8192]
    # PNG / typical 8-bit signatures including 0x89 PNG \r\n \x1a \n.
    if sample.startswith(b"\x89PNG") or sample.startswith(b"\xff\xd8\xff"):
        return True
    textish = 0
    for b in sample:
        if b in (9, 10, 13) or 32 <= b <= 126:
            textish += 1
    return textish / len(sample) < 0.85


def bytes_for_hash(data: bytes) -> bytes:
    if looks_binary(data):
        return data
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_raw(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_normalised(data: bytes) -> str:
    return hashlib.sha256(bytes_for_hash(data)).hexdigest()


def classify_pair(left: bytes, right: bytes) -> str:
    if sha256_raw(left) == sha256_raw(right):
        return IDENTICAL
    if sha256_normalised(left) == sha256_normalised(right):
        return IDENTICAL_MODULO_EOL
    return CONTENT_DIVERGED
