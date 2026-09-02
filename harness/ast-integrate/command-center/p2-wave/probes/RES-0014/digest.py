"""LF-normalised sha256 used by G-1 measure."""
from __future__ import annotations

import hashlib
from pathlib import Path


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def digest_file(path: Path) -> tuple[str, int]:
    return digest_bytes(path.read_bytes())
