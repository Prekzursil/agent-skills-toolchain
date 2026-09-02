#!/usr/bin/env python3
"""Find harvested copies of missing shard-23 modules (scoped, no full-tree rg)."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
NAMES = [
    "repro_gate.py",
    "legacy_layout_steps.py",
    "ast_compose.py",
    "replace.py",
    "intake.py",
    "durability.py",
    "strict_json.py",
    "permission_diff.py",
    "clock.py",
    "progress.py",
    "spec.py",
    "harness.py",
]
ROOTS = [
    REPO / "tools" / "plugin",
    REPO / "tools" / "agentspec",
    REPO / "tools" / "library",
    REPO / "tools" / "council",
    REPO / "tools" / "marketplace",
    REPO / "plugin",
    REPO / "command-center" / "p2-wave" / "probes" / "IMP-0011",
    REPO / "command-center" / "p2-wave" / "probes" / "IMP-0049",
    REPO / "command-center" / "p2-wave" / "probes" / "IMP-0087",
    REPO / "command-center" / "p2-wave" / "probes" / "ADV-0060",
    REPO / "command-center" / "p2-wave" / "probes" / "IMP-0254",
    REPO / "command-center" / "p2-wave" / "probes" / "IMP-0275",
    REPO / "command-center" / "p2-wave" / "probes" / "IMP-0371",
    REPO / "command-center" / "p2-wave" / "probes" / "SYN-0046",
    REPO / "command-center" / "p2-wave" / "probes" / "TST-0252",
    REPO / "command-center" / "p2-wave" / "ovh-monitor" / "delivery-pull",
    REPO / "command-center" / "p2-wave" / "ovh-monitor" / "error-pull",
    REPO / "command-center" / "p2-wave" / "ovh-monitor" / "g1-shards",
]
# depth-limited walk
MAX_DEPTH = 8

def walk(root: Path, depth: int = 0):
    if depth > MAX_DEPTH:
        return
    try:
        kids = list(root.iterdir())
    except OSError:
        return
    for p in kids:
        name = p.name
        if name in {".git", "node_modules", "__pycache__", ".venv"}:
            continue
        if p.is_file() and name in NAMES:
            yield p
        elif p.is_dir():
            yield from walk(p, depth + 1)

hits: dict[str, list[str]] = {n: [] for n in NAMES}
for root in ROOTS:
    if not root.exists():
        continue
    for p in walk(root):
        rel = str(p.relative_to(REPO)).replace("\\", "/")
        hits[p.name].append(rel)

for n, paths in hits.items():
    print(f"\n== {n} n={len(paths)}")
    for p in paths[:12]:
        print(" ", p)
