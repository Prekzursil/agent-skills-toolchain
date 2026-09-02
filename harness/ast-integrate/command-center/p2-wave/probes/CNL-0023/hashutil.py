"""LF-normalized sha256 used by CNL-0023 provenance records."""
from __future__ import annotations

import hashlib
from pathlib import Path


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())
