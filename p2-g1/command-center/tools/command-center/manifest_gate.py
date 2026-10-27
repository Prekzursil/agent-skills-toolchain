"""Manifest digest helpers for SYN-0019."""
from __future__ import annotations

import hashlib
from pathlib import Path


def lf_digest(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def digest_file(path: Path) -> tuple[str, int]:
    return lf_digest(Path(path).read_bytes())
