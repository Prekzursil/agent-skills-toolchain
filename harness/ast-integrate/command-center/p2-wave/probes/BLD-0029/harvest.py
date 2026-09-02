"""Harvest residual / UNVERIFIED / NOT-CHECKED result tags (use, not mention)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TAGS = frozenset({"UNVERIFIED", "NOT-CHECKED"})
SKIP_KEYS = frozenset({"enum", "examples", "documentation", "description", "$comment"})
SKIP_NAME_SUFFIXES = ("_validate_out.json", "_revalidate_out.json")
EXPERIMENT_KEYS = (
    "settling_experiment",
    "named_experiment",
    "named_settling_experiment",
    "experiment",
)
IMPACT_KEYS = (
    "owner_visible_impact",
    "owner_impact",
    "impact",
    "impact_statement",
)


def _skip_file(rel: str, name: str, *, skip_self: bool) -> bool:
    posix = rel.replace("\\", "/")
    if name == "WORK-UNIT-CATALOG.json":
        return True
    if "/schema/" in f"/{posix}":
        return True
    if name.endswith(SKIP_NAME_SUFFIXES):
        return True
    if skip_self:
        parts = posix.split("/")
        if "BLD-0029" in parts:
            return True
        if name == "BLD-0029.json" and posix.startswith("command-center/receipts/"):
            return True
        # Live residuals are lane artifacts. Probe fixture corpora (ADV-0002
        # outcome copies of receipts, planted controls, seeds) reuse
        # UNVERIFIED/NOT-CHECKED as copied JSON and must not drift harvest.
        if "/p2-wave/probes/" in f"/{posix}/" and "/fixtures/" in posix:
            return True
    return False


def _sibling_text(parent: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        val = parent.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, dict) and val:
            return json.dumps(val, sort_keys=True)
    return ""


def _walk(
    obj: Any,
    path: str,
    parent_key: str,
    parent: dict | None,
    out: list[dict],
    rel: str,
) -> None:
    if isinstance(obj, dict):
        for key, val in obj.items():
            child = f"{path}.{key}"
            _walk(val, child, key, obj, out, rel)
        return
    if isinstance(obj, list):
        for i, val in enumerate(obj):
            _walk(val, f"{path}[{i}]", parent_key, parent, out, rel)
        return
    if not isinstance(obj, str) or obj not in TAGS:
        return
    if parent_key in SKIP_KEYS or ".enum" in path:
        return
    parent = parent or {}
    tag = {
        "id": f"tag:{rel}:{path}",
        "source_path": rel,
        "json_path": path,
        "key": parent_key,
        "tag": obj,
        "claim": str(parent.get("claim") or parent.get("id") or parent.get("path") or ""),
        "experiment_text": _sibling_text(parent, EXPERIMENT_KEYS),
        "impact_text": _sibling_text(parent, IMPACT_KEYS),
    }
    out.append(tag)


def harvest_tree(root: Path, repo: Path, *, skip_self: bool = False) -> list[dict]:
    tags: list[dict] = []
    for path in sorted(root.rglob("*.json")):
        rel = path.relative_to(repo).as_posix()
        if _skip_file(rel, path.name, skip_self=skip_self):
            continue
        if path.stat().st_size > 8_000_000:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        found: list[dict] = []
        _walk(data, "$", "", None, found, rel)
        tags.extend(found)
    tags.sort(key=lambda t: (t["source_path"], t["json_path"]))
    return tags


def harvest_live(repo: Path) -> list[dict]:
    return harvest_tree(repo / "command-center", repo, skip_self=True)


harvest_tree = harvest_tree
harvest_live = harvest_live
