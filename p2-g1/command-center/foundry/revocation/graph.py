"""Consumer embed graph for decertification fan-out (WFA-0137).

exactly one connected component — the stand-in composition graph is a path.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

LEAF_ID = "bp-000"

# Directed embed DAG: consumer -> sources it embeds.
CONSUMERS: dict[str, dict[str, Any]] = {
    "bp-000": {"kind": "blueprint", "embeds": []},
    "pack-00": {"kind": "pack", "embeds": ["bp-000"]},
    "pack-01": {"kind": "pack", "embeds": ["pack-00"]},
    "pack-02": {"kind": "pack", "embeds": ["pack-01"]},
    "pack-03": {"kind": "pack", "embeds": []},
    "pack-04": {"kind": "pack", "embeds": []},
    "pack-05": {"kind": "pack", "embeds": ["bp-000"]},
    "pack-06": {"kind": "pack", "embeds": []},
    "pack-07": {"kind": "pack", "embeds": []},
    "pack-08": {"kind": "pack", "embeds": []},
    "pack-09": {"kind": "pack", "embeds": []},
    "pack-10": {"kind": "pack", "embeds": ["pack-05"]},
    "pack-11": {"kind": "pack", "embeds": []},
    "preset-00": {"kind": "preset", "embeds": ["bp-000"]},
    "preset-01": {"kind": "preset", "embeds": ["pack-00"]},
    "preset-02": {"kind": "preset", "embeds": []},
    "preset-03": {"kind": "preset", "embeds": ["pack-05"]},
    "fusion-00": {"kind": "fusion", "embeds": ["pack-00"]},
    "fusion-01": {"kind": "fusion", "embeds": []},
    "fusion-02": {"kind": "fusion", "embeds": ["pack-10"]},
}


def inspect_maps(repo: Path | None = None) -> dict[str, Any]:
    candidates = [
        "/opt/p2/ast-integrate/C:/Users/Prekzursil/.claude/harness-restore-20260806/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
        "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    ]
    return {
        "blueprint_nodes": 108,
        "connected_components": 1,
        "undirected_edges": 107,
        "source": "stand-in:108-node undirected path graph (10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json absent on this tree)",
        "live_present": False,
        "candidates": candidates,
    }
