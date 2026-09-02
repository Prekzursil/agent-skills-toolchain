"""CRLF-normalized sha256. Same rule as render_manifest and unit_manifest."""
from __future__ import annotations

import hashlib
from pathlib import Path


def digest_bytes(raw: bytes) -> tuple[str, int]:
    normalized = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(normalized).hexdigest(), len(normalized)


def digest_file(path: Path) -> tuple[str, int]:
    return digest_bytes(path.read_bytes())
