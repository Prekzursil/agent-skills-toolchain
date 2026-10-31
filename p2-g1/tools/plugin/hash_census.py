"""Path -> sha256 census and diff (IMP-0049)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def _digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def file_digest(path: Path) -> str:
    return _digest(Path(path).read_bytes())


def hash_census(root: Path) -> dict[str, str]:
    root = Path(root)
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = _digest(p.read_bytes())
    return out


def census_diff(before: dict[str, str], after: dict[str, str]) -> dict[str, Any]:
    before = dict(before or {})
    after = dict(after or {})
    missing = sorted(set(before) - set(after))
    extra = sorted(set(after) - set(before))
    changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])
    return {
        "equal": not missing and not extra and not changed,
        "missing": missing,
        "extra": extra,
        "changed": changed,
    }
