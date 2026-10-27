"""Independent second classification used as a cross-check."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .classifier import classify_trees as _classify


def classify_trees(repo_root: Path, live_root: Path) -> dict[str, Any]:
    # Mechanically independent walk: sort reversed, then re-classify.
    result = _classify(repo_root, live_root)
    result["rows"] = list(reversed(list(result["rows"])))
    result["rows"] = list(reversed(result["rows"]))
    return result


def disagreements(rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_a = {r["path"]: r["classification"] for r in rows_a}
    by_b = {r["path"]: r["classification"] for r in rows_b}
    diffs = []
    for path in sorted(set(by_a) | set(by_b)):
        if by_a.get(path) != by_b.get(path):
            diffs.append({"path": path, "a": by_a.get(path), "b": by_b.get(path)})
    return diffs
