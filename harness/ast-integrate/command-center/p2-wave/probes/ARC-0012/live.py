"""Run both completeness directions against THIS worktree.

Primary pairing: ARC-0010 registry.json (the typed A2 registry that exists
on disk) vs command-center/control-plane/A2/generated/ (the A2 output root
specified by mapping.py). A2 DESIGN.json is absent; the registry is the
live stand-in, disclosed as such.

Supporting pairing: the seven A2 dossier catalog output_path rows vs files
under command-center/phase3/A2/. Reported separately, never added to the
primary counts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from completeness import completeness, load_registry
from mapping import GENERATED_ROOT

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REGISTRY_REL = "command-center/p2-wave/probes/ARC-0010/registry.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
A2_UNIT_IDS = (
    "ARC-0010",
    "ARC-0011",
    "ARC-0012",
    "ARC-0013",
    "ARC-0014",
    "ARC-0015",
    "ARC-0016",
)


def primary(repo: Path = REPO) -> dict[str, Any]:
    reg_path = repo / REGISTRY_REL
    registry = load_registry(reg_path)
    result = completeness(repo, registry, GENERATED_ROOT)
    result["pairing"] = "a2-registry-vs-generated"
    result["registry_path"] = REGISTRY_REL
    result["registry_present"] = True
    result["design_path"] = "command-center/phase3/A2/DESIGN.json"
    result["design_present"] = (repo / "command-center/phase3/A2/DESIGN.json").is_file()
    return result


def a2_dossier_catalog_slice(repo: Path = REPO) -> dict[str, Any]:
    """Supporting analogue: catalog output_path vs disk, A2 units only."""
    catalog = json.loads((repo / CATALOG_REL).read_text(encoding="utf-8"))
    units = catalog.get("work_units") or []
    rows = [u for u in units if isinstance(u, dict) and u.get("id") in A2_UNIT_IDS]
    direction_a: list[dict[str, str]] = []
    named: set[str] = set()
    for u in rows:
        rel = str(u.get("output_path") or "").replace("\\", "/")
        if not rel:
            direction_a.append({"id": str(u.get("id")), "reason": "no-output_path"})
            continue
        named.add(rel)
        path = repo / rel
        if not path.is_file() or path.stat().st_size < 1:
            direction_a.append(
                {
                    "id": str(u.get("id")),
                    "expected_path": rel,
                    "reason": "missing" if not path.is_file() else "empty",
                }
            )
    a2_root = repo / "command-center/phase3/A2"
    on_disk: list[str] = []
    if a2_root.is_dir():
        for p in sorted(a2_root.rglob("*")):
            if p.is_file():
                on_disk.append(p.relative_to(repo).as_posix())
    direction_b = [
        {"path": rel, "reason": "unregistered"}
        for rel in on_disk
        if rel not in named
    ]
    return {
        "pairing": "a2-dossier-catalog-vs-phase3-A2",
        "note": (
            "Supporting analogue only. Not added to the primary registry/"
            "generated counts. Catalog is not the A2 generator registry."
        ),
        "registry_entry_count": len(rows),
        "output_file_count": len(on_disk),
        "direction_a_orphan_registry_count": len(direction_a),
        "direction_a_orphans": direction_a,
        "direction_b_orphan_output_count": len(direction_b),
        "direction_b_orphans": direction_b,
        "direction_a_fail": bool(direction_a),
        "direction_b_fail": bool(direction_b),
    }


def live_report(repo: Path = REPO) -> dict[str, Any]:
    p = primary(repo)
    s = a2_dossier_catalog_slice(repo)
    fails = []
    if p["direction_a_fail"]:
        fails.append("direction_a")
    if p["direction_b_fail"]:
        fails.append("direction_b")
    return {
        "primary": p,
        "supporting_catalog_slice": s,
        "fails_today": fails,
        "direction_a_orphan_registry_count": p["direction_a_orphan_registry_count"],
        "direction_b_orphan_output_count": p["direction_b_orphan_output_count"],
    }


if __name__ == "__main__":
    print(json.dumps(live_report(), indent=2, sort_keys=True))
