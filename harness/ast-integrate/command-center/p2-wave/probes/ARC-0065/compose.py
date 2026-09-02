"""Compose a capability-to-authority table from live A1/A2/A6 dossiers.

Maximal hybrid (catalog ARC-0059): keep the strongest mechanism from each
architecture. That union is the composition under test. A9/DESIGN.json is
not authored here (no ADV rebuild). Missing A3-A5/A7-A8 dossiers are
recorded absent rather than invented.

One cell = one (capability, authority). A capability with two authorities
is a P0 duplicate. Agreement of payloads across two authorities is not
singularity.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

A1_DESIGN = "command-center/phase3/A1/DESIGN.json"
A2_DESIGN = "command-center/phase3/A2/DESIGN.json"
A6_DESIGN = "command-center/phase3/A6/DESIGN.json"
A9_DESIGN = "command-center/phase3/A9/DESIGN.json"

A1_ROLE_TO_CAP = {
    "skills": "skills",
    "hooks": "hooks",
    "rules": "rules",
    "mcp-mounts": "mcp",
    "workflow-blueprints": "workflows",
    "council-protocols": "council",
    "council-presets": "council",
    "index": "capability-index",
}
A2_ROLE_TO_CAP = {
    "skill-deployments": "skills",
    "hook-deployments": "hooks",
    "rule-deployments": "rules",
    "plugin-manifest": "plugin",
    "marketplace-entries": "marketplace",
    "docs": "docs",
    "workflow-catalog": "workflows",
    "council-catalog": "council",
}
A6_ROLE_TO_CAP = {
    "work-unit-and-artifact-contract": "work-unit-contract",
    "vendor-adapter": "vendor-tools",
    "negotiation-algorithm": "vendor-tools",
}

NAMED_CAPABILITY = "skills"
NAMED_A = "A1-manifest-loader"
NAMED_B = "A2-ssot-generator"

# Unique snippets used to pin table rows to DESIGN file:line.
A1_SKILLS_SNIPPET = "One file per skill id."
A2_SKILLS_SNIPPET = "Generated SKILL.md with provenance header."


def _load_json(rel: str) -> dict[str, Any] | None:
    path = REPO / rel
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _rows_from_file_set(
    design: dict[str, Any],
    architecture_id: str,
    authority: str,
    role_map: dict[str, str],
    source_path: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in design.get("file_set") or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        cap = role_map.get(role)
        if not cap:
            continue
        key = (cap, authority)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "capability": cap,
                "authority": authority,
                "architecture_id": architecture_id,
                "source_path": source_path,
                "source_role": role,
                "source_file": str(item.get("path") or ""),
            }
        )
    return out


def extract_table(architectures: tuple[str, ...]) -> list[dict[str, Any]]:
    """Union of authorities for the named architectures (maximal = all of them)."""
    rows: list[dict[str, Any]] = []
    if "A1" in architectures:
        doc = _load_json(A1_DESIGN)
        if doc is None:
            raise FileNotFoundError(A1_DESIGN)
        rows.extend(_rows_from_file_set(doc, "A1", NAMED_A, A1_ROLE_TO_CAP, A1_DESIGN))
    if "A2" in architectures:
        doc = _load_json(A2_DESIGN)
        if doc is None:
            raise FileNotFoundError(A2_DESIGN)
        rows.extend(_rows_from_file_set(doc, "A2", NAMED_B, A2_ROLE_TO_CAP, A2_DESIGN))
    if "A6" in architectures:
        doc = _load_json(A6_DESIGN)
        if doc is None:
            raise FileNotFoundError(A6_DESIGN)
        rows.extend(
            _rows_from_file_set(doc, "A6", "A6-vendor-adapter", A6_ROLE_TO_CAP, A6_DESIGN)
        )
    rows.sort(key=lambda r: (r["capability"], r["authority"]))
    return rows


def duplicate_classes(table: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_cap: dict[str, set[str]] = defaultdict(set)
    for row in table:
        by_cap[str(row["capability"])].add(str(row["authority"]))
    return {cap: sorted(auths) for cap, auths in sorted(by_cap.items()) if len(auths) > 1}


def adjacent_named_pair(table: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The two skills rows sit next to each other in the sorted table."""
    hits = [
        r
        for r in table
        if r.get("capability") == NAMED_CAPABILITY
        and r.get("authority") in {NAMED_A, NAMED_B}
    ]
    hits.sort(key=lambda r: str(r["authority"]))
    return hits


def load_a1_ids(root: Path) -> dict[str, Any]:
    import sys

    loader_dir = REPO / "command-center/p2-wave/probes/ARC-0009"
    sys.path.insert(0, str(loader_dir))
    import a1_loader as L  # noqa: E402

    return L.load_a1(root)


def load_a2_skill_ids(registry: Path) -> list[str]:
    doc = json.loads(registry.read_text(encoding="utf-8"))
    entries = doc.get("entries") if isinstance(doc, dict) else None
    if not isinstance(entries, list):
        raise ValueError(f"A2 registry missing entries: {registry}")
    ids = [
        str(e.get("id"))
        for e in entries
        if isinstance(e, dict) and str(e.get("kind") or "") == "skill"
    ]
    return sorted(ids)


def split_brain(a1_ids: list[str], a2_ids: list[str]) -> dict[str, Any]:
    s1, s2 = set(a1_ids), set(a2_ids)
    only_a1 = sorted(s1 - s2)
    only_a2 = sorted(s2 - s1)
    return {
        "only_a1": only_a1,
        "only_a2": only_a2,
        "drift_count": len(only_a1) + len(only_a2),
        "agree": sorted(s1 & s2),
    }


def compare_objective(
    hybrid_dup: int,
    hybrid_drift: int,
    single_dup: int,
    single_drift: int,
) -> dict[str, Any]:
    """Correctness first: lexicographic (dup, drift), lower is better."""
    j_h = (int(hybrid_dup), int(hybrid_drift))
    j_s = (int(single_dup), int(single_drift))
    return {
        "hybrid_J": list(j_h),
        "best_single_J": list(j_s),
        "hybrid_worse": j_h > j_s,
        "hybrid_confirmed": j_h < j_s,
        "tie": j_h == j_s,
    }


def a9_design_present() -> bool:
    return (REPO / A9_DESIGN).is_file()


def missing_source_dossiers() -> dict[str, bool]:
    return {
        "A1": (REPO / A1_DESIGN).is_file(),
        "A2": (REPO / A2_DESIGN).is_file(),
        "A3": (REPO / "command-center/phase3/A3/DESIGN.json").is_file(),
        "A4": (REPO / "command-center/phase3/A4/DESIGN.json").is_file(),
        "A5": (REPO / "command-center/phase3/A5/DESIGN.json").is_file(),
        "A6": (REPO / A6_DESIGN).is_file(),
        "A7": (REPO / "command-center/phase3/A7/DESIGN.json").is_file(),
        "A8": (REPO / "command-center/phase3/A8/DESIGN.json").is_file(),
        "A9": a9_design_present(),
    }
