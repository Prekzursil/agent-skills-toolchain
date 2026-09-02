"""Read a path as LF-normalised content bytes (committed blob when git exists).

CC-0001 harness uses ``content_bytes`` on isolated REGISTER.md fixtures that are
not git blobs, so the fallback is LF-normalised working-tree bytes.
"""
from __future__ import annotations

from pathlib import Path

try:
    from blob import provenance_bytes as _provenance_bytes
except Exception:  # pragma: no cover - isolated import
    _provenance_bytes = None  # type: ignore[assignment]


def content_bytes(path: str | Path) -> bytes:
    p = Path(path)
    if _provenance_bytes is not None:
        try:
            return _provenance_bytes(p)
        except Exception:
            pass
    return p.read_bytes().replace(b"\r\n", b"\n")


def read_blob(path: str, rev: str = "HEAD", *, repo: Path | None = None) -> bytes:
    del rev, repo
    return content_bytes(path)
