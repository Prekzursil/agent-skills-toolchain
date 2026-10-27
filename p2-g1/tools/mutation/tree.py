"""Subject-tree fingerprint for mutation isolation (TST-0119)."""
from __future__ import annotations

import hashlib
from pathlib import Path


def tree_fingerprint(root: str | Path) -> str:
    root = Path(root)
    h = hashlib.sha256()
    if root.is_file():
        h.update(root.read_bytes())
        return h.hexdigest()
    if not root.is_dir():
        return h.hexdigest()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        h.update(path.relative_to(root).as_posix().encode())
        h.update(path.read_bytes())
    return h.hexdigest()


__all__ = ["tree_fingerprint"]
