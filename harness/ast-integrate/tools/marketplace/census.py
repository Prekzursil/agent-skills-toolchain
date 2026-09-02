"""Content-addressed file census of a tree (path -> sha256)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def census(root: str | Path) -> dict[str, str]:
    root = Path(root)
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for dirpath, dirnames, filenames in __import__("os").walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__", "node_modules"}]
        for name in filenames:
            p = Path(dirpath) / name
            try:
                rel = p.relative_to(root).as_posix()
                out[rel] = _sha(p)
            except OSError:
                continue
    return out


def subset(census_map: dict[str, str], paths) -> dict[str, str]:
    wanted = {str(p).replace("\\", "/") for p in (paths or [])}
    return {k: v for k, v in (census_map or {}).items() if k in wanted}


def scan(*args: Any, **kwargs: Any) -> dict[str, str]:
    root = args[0] if args else kwargs.get("root")
    return census(root) if root is not None else {}
