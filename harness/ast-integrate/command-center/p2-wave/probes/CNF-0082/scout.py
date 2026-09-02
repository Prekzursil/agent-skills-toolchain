"""Probe-local workflow scout for CNF-0082.

Declared mechanism: walk each source-class directory for workflow JSON
documents and match goal tokens. Does not read index.json (injection trap).
Always appends a rebuild proposal so ranking vs BUILD is observable.
"""
from __future__ import annotations

import json
from pathlib import Path

from scenario import (
    GOAL_TOKENS,
    REBUILD_SCORE,
    SOURCE_CLASSES,
)


def tokens_cover(doc_tokens, goal_tokens) -> bool:
    have = {str(t).lower() for t in (doc_tokens or [])}
    need = {str(t).lower() for t in goal_tokens}
    return need.issubset(have)


def search(
    fixture_root: Path,
    goal_tokens=GOAL_TOKENS,
    source_classes=None,
    include_rebuild: bool = True,
    rebuild_score: int = REBUILD_SCORE,
) -> list[dict]:
    hits: list[dict] = []
    classes = tuple(source_classes) if source_classes is not None else SOURCE_CLASSES
    root = Path(fixture_root)
    for cls in classes:
        class_dir = root / "sources" / cls
        if not class_dir.is_dir():
            continue
        for path in sorted(class_dir.rglob("*.json")):
            if path.name == "index.json":
                continue
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            if not tokens_cover(doc.get("goal_tokens"), goal_tokens):
                continue
            rel = path.as_posix()
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                pass
            hits.append(
                {
                    "id": str(doc.get("id") or path.stem),
                    "kind": "existing-workflow",
                    "path": rel,
                    "quality_score": int(doc.get("quality_score") or 0),
                    "source_class": cls,
                    "superior": bool(doc.get("superior")),
                    "title": str(doc.get("title") or path.stem),
                }
            )
    if include_rebuild:
        hits.append(
            {
                "id": "build.new.certify-and-publish-workflow",
                "kind": "rebuild-proposal",
                "path": None,
                "quality_score": int(rebuild_score),
                "source_class": "generator",
                "superior": False,
                "title": "Rebuild certify-and-publish from scratch",
            }
        )
    return rank(hits)


def rank(hits: list[dict]) -> list[dict]:
    ordered = sorted(
        hits,
        key=lambda h: (-int(h.get("quality_score") or 0), str(h.get("id") or "")),
    )
    for i, row in enumerate(ordered, 1):
        row["rank"] = i
    return ordered
