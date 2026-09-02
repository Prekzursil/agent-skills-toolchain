"""Independent path census (find/du class). Disagreement with the scanner is a detector failure."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable


def _posix(rel: str) -> str:
    return str(rel).replace("\\", "/").strip("/")


def census(root: Path) -> dict[str, Any]:
    root = Path(root)
    paths: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in filenames:
            p = Path(dirpath) / name
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                continue
            paths.append(_posix(rel))
    paths = sorted(set(paths))
    return {
        "paths": paths,
        "path_count": len(paths),
        "enumerator": "os.walk-independent",
    }


def plugin_root(dest_root: Path, name: str) -> Path:
    return Path(dest_root) / "plugins" / str(name)


def tree_files(root: Path) -> dict[str, str]:
    root = Path(root)
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        for name in filenames:
            p = Path(dirpath) / name
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                continue
            out[rel] = "file"
    return out


def owned_remaining(home: Path, projection: Any) -> list[str]:
    home = Path(home)
    rels = []
    if hasattr(projection, "owned_relpaths"):
        rels = list(projection.owned_relpaths())
    elif isinstance(projection, dict):
        rels = list(projection.get("owned") or [])
    leftover = []
    for rel in rels:
        if (home / rel).exists():
            leftover.append(str(rel).replace("\\", "/"))
    return leftover


def non_owned_inventory(
    home: Path, projection: Any, include_user_data: bool = True
) -> dict[str, str]:
    import hashlib

    home = Path(home)
    owned = set()
    if hasattr(projection, "owned_relpaths"):
        owned = {str(x).replace("\\", "/") for x in projection.owned_relpaths()}
    walked = census(home)["paths"]
    inventory: dict[str, str] = {}
    for rel in walked:
        if rel in owned:
            continue
        path = home / rel
        if not path.is_file():
            continue
        inventory[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not include_user_data:
        inventory = {k: v for k, v in inventory.items() if not k.startswith("user-data/")}
    return inventory


def compare(left: Iterable[str], right: Iterable[str]) -> dict[str, Any]:
    a = {_posix(x) for x in left}
    b = {_posix(x) for x in right}
    return {
        "agree": a == b,
        "only_left": sorted(a - b),
        "only_right": sorted(b - a),
        "left_count": len(a),
        "right_count": len(b),
    }
