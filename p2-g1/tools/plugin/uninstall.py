"""Uninstall owned plugin paths while retaining user data (IMP-0027)."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


class UninstallError(Exception):
    pass


def uninstall(home: Path, projection: Any, purge_user_data: bool = False) -> dict[str, Any]:
    home = Path(home)
    rels = []
    if hasattr(projection, "owned_relpaths"):
        rels = list(projection.owned_relpaths())
    elif isinstance(projection, dict):
        rels = list(projection.get("owned") or [])
    removed = []
    for rel in rels:
        path = home / rel
        if path.is_file():
            path.unlink()
            removed.append(str(rel))
        elif path.is_dir():
            shutil.rmtree(path)
            removed.append(str(rel))
    if purge_user_data:
        user_root = home / "user-data"
        if user_root.exists():
            shutil.rmtree(user_root)
    # prune empty owned directories
    for rel in sorted(rels, key=lambda r: r.count("/"), reverse=True):
        parent = (home / rel).parent
        if parent != home and parent.is_dir() and not any(parent.iterdir()):
            try:
                parent.rmdir()
            except OSError:
                pass
    return {"removed": removed, "purge_user_data": bool(purge_user_data)}


def uninstall_plugin(*args, **kwargs):
    return uninstall(*args, **kwargs)
