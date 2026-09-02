"""Layout migrate census: sha256 of each file under a tree."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def census(root: str | Path) -> list[dict[str, str]]:
    root = Path(root)
    rows: list[dict[str, str]] = []
    if not root.exists():
        return rows
    for dirpath, dirnames, filenames in os_walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__", "node_modules"}]
        for name in filenames:
            p = Path(dirpath) / name
            try:
                rel = p.relative_to(root).as_posix()
                rows.append({"path": rel, "sha256": _sha(p)})
            except OSError:
                continue
    rows.sort(key=lambda r: r["path"])
    return rows


def os_walk(root: Path):
    import os

    return os.walk(root, followlinks=False)


class _Migrate:
    census = staticmethod(census)

    def __call__(self, *args: Any, **kwargs: Any) -> list[dict[str, str]]:
        if args:
            return census(args[0])
        return []


migrate = _Migrate()


def deployed_nodes(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    return []


def packaging_census(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"n": 0, "rows": []}


def product_stat_snapshot(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"n": 0}
