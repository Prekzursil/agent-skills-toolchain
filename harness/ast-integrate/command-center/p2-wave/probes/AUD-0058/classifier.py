"""Frontmatter-only declared load-class census (probe 1).

This detector never inspects a context bag. It only parses the YAML fence
and classifies:

  * no fence, or fence without a `paths` key -> ALWAYS-ON
  * fence with a `paths` key (any value, including ["**/*"]) -> LAZY
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from frontmatter import paths_key_present, split_frontmatter
from loader import cap_id_for, iter_capability_files


def classify_file(root: Path, path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    paths_present = paths_key_present(fm)
    globs: list[str] = []
    if paths_present and fm is not None:
        raw = fm.get("paths")
        if isinstance(raw, list):
            globs = [str(x) for x in raw]
        elif raw is not None:
            globs = [str(raw)]
    declared = "LAZY" if paths_present else "ALWAYS-ON"
    name = ""
    description = ""
    if isinstance(fm, dict):
        name = str(fm.get("name") or "")
        description = str(fm.get("description") or "")
    return {
        "id": cap_id_for(root, path),
        "rel_path": path.relative_to(root).as_posix(),
        "kind": "skill" if path.name == "SKILL.md" else "rule",
        "has_frontmatter": fm is not None,
        "paths_key_present": paths_present,
        "path_globs": globs,
        "declared_load_class": declared,
        "name": name,
        "description": description,
        "body_bytes": len(body.encode("utf-8")),
        "sha256": _sha(text),
    }


def classify_tree(root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    return [classify_file(root, p) for p in iter_capability_files(root)]


def _sha(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()
