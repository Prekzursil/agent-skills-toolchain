"""Local repository discovery adapter (IMP-0150)."""
from __future__ import annotations

from .local_repo import (
    ArchiveForbidden,
    Candidate,
    as_dicts,
    discover_local,
    fetch_bytes,
    find_path,
    git_bytes,
    sha256_bytes,
)

__all__ = [
    "ArchiveForbidden",
    "Candidate",
    "as_dicts",
    "discover_local",
    "fetch_bytes",
    "find_path",
    "git_bytes",
    "sha256_bytes",
]
