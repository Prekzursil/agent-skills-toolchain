"""Canonical JSON serialization and content-address digests (TST-0301).

The B07 margin table is frozen by content address, not by git commit, so the
bytes that are hashed must be reproducible: ``canonical_bytes`` is the single
serialization used both to write documents and to bind them.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

__all__ = ["canonical_bytes", "digest_bytes", "digest_document", "digest_file", "write_json"]


def canonical_bytes(doc: Any) -> bytes:
    """Deterministic UTF-8 encoding of ``doc`` (sorted keys, 2-space indent, LF)."""
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return text.encode("utf-8")


def digest_bytes(raw: bytes) -> tuple[str, int]:
    """sha256 hex digest and length of ``raw`` after CRLF -> LF normalisation."""
    normalised = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(normalised).hexdigest(), len(normalised)


def digest_document(doc: Any) -> str:
    """sha256 of the canonical serialization of an in-memory document."""
    return digest_bytes(canonical_bytes(doc))[0]


def digest_file(path: str | os.PathLike[str]) -> tuple[str, int]:
    """sha256 hex digest and byte count of the file at ``path`` (LF-normalised)."""
    return digest_bytes(Path(path).read_bytes())


def write_json(dest: str | os.PathLike[str], doc: Any) -> tuple[str, int]:
    """Write ``doc`` canonically to ``dest`` and return ``(sha256, bytes)``.

    A document written here digests identically via ``digest_file`` and
    ``digest_document``; that identity is what lets a comparison bind the table
    it was scored against.
    """
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_bytes(doc)
    path.write_bytes(raw)
    return digest_bytes(raw)
