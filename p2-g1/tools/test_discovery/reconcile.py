"""Reconcile collected tests against a registry (orphans vs ghosts)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .collect import collect_tree, collect_tree_cli
from .walker import walk_tree


@dataclass
class ReconcileResult:
    complete: bool
    paths_walked: int
    orphans: list[str] = field(default_factory=list)
    ghosts: list[str] = field(default_factory=list)
    collected_count: int = 0
    registered_and_collected: list[str] = field(default_factory=list)
    collector: str = "test_discovery.collect"
    errors: list[str] = field(default_factory=list)


def reconcile_tree(root: Path, registry: Path, via_cli: bool = False) -> ReconcileResult:
    root = Path(root)
    walk = walk_tree(root)
    collected = collect_tree_cli(root) if via_cli else collect_tree(root)
    nodeids = collected.nodeids()
    try:
        doc = json.loads(Path(registry).read_text(encoding="utf-8"))
        registered = [str(x) for x in (doc.get("tests") or [])]
    except (OSError, json.JSONDecodeError):
        registered = []
    coll_set = set(nodeids)
    reg_set = set(registered)
    orphans = sorted(coll_set - reg_set)
    ghosts = sorted(reg_set - coll_set)
    both = sorted(coll_set & reg_set)
    return ReconcileResult(
        complete=walk.complete and not walk.errors,
        paths_walked=walk.paths_walked or walk.paths_visited,
        orphans=orphans,
        ghosts=ghosts,
        collected_count=len(nodeids),
        registered_and_collected=both,
        collector=collected.collector,
        errors=list(walk.errors),
    )
