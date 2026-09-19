"""Shared cache-free detector for AUD-0091, imported by both the control and probe1.

A single function so the control's fixture demonstration and probe1's real
precheck of the clean-room npm cache directory are provably the SAME logic,
not two detectors that happen to agree by coincidence.
"""

from __future__ import annotations

from pathlib import Path


def list_entries(path: Path) -> list[str]:
    """Every file/dir under path, relative paths, sorted. Empty list if path
    is absent or truly empty -- absence and emptiness are both cache-free."""
    if not path.exists():
        return []
    return sorted(str(p.relative_to(path)) for p in path.rglob("*"))


def is_cache_free(path: Path) -> dict:
    entries = list_entries(path)
    return {
        "path": str(path),
        "existed": path.exists(),
        "entry_count": len(entries),
        "entries_sample": entries[:20],
        "cache_free": len(entries) == 0,
    }
