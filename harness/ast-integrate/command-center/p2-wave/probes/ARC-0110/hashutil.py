#!/usr/bin/env python3
"""LF-canonical sha256 used by the freeze manifest and the G-1 measure script."""
from __future__ import annotations

import hashlib
from pathlib import Path


def digest_bytes(raw: bytes) -> tuple[str, int]:
    canon = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(canon).hexdigest(), len(canon)


def digest_file(path: Path) -> tuple[str, int]:
    return digest_bytes(path.read_bytes())


def digest_hex(raw: bytes) -> str:
    return digest_bytes(raw)[0]
