"""Independent file count: os.listdir recursion (not os.scandir)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def listdir_tree(root: Path) -> dict[str, Any]:
    rels: list[str] = []
    errors: list[dict[str, str]] = []

    def rec(dir_native: Path, parts: tuple[str, ...]) -> None:
        try:
            names = os.listdir(dir_native)
        except OSError as exc:
            errors.append(
                {
                    "rel": "/".join(parts) if parts else ".",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            return
        for name in names:
            child_parts = parts + (name,)
            rel = "/".join(child_parts)
            path = dir_native / name
            try:
                is_dir = path.is_dir() and not path.is_symlink()
                is_file = path.is_file() and not path.is_symlink()
            except OSError as exc:
                errors.append({"rel": rel, "error": f"{type(exc).__name__}: {exc}"})
                continue
            if is_dir:
                rec(path, child_parts)
            elif is_file:
                rels.append(rel)

    rec(Path(root), ())
    complete = not errors
    return {
        "api": "os.listdir-recursive",
        "root": str(root),
        "complete": complete,
        "count": len(rels) if complete else None,
        "rels": sorted(rels),
        "errors": errors,
    }
