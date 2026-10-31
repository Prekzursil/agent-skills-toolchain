"""Expand a projection map into the live touch set (IMP-0030)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_projection(path: Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(path, dict):
        return path
    return json.loads(Path(path).read_text(encoding="utf-8"))


def expand_touch_paths(root: Path, projection: dict[str, Any] | Path) -> list[str]:
    root = Path(root)
    proj = load_projection(projection) if not isinstance(projection, dict) else projection
    out: list[str] = []
    for entry in proj.get("entries") or []:
        rel = str(entry.get("live_path") or "").replace("\\", "/").strip("/")
        if not rel:
            continue
        live = root / rel
        if live.is_file():
            out.append(rel)
            continue
        if live.is_dir():
            for p in live.rglob("*"):
                if p.is_file():
                    out.append(p.relative_to(root).as_posix())
    # unique, stable
    seen: set[str] = set()
    ordered: list[str] = []
    for rel in out:
        if rel not in seen:
            seen.add(rel)
            ordered.append(rel)
    return ordered
