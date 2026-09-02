"""Declared, versioned capability taxonomy and coverage vectors.

Coverage is a 0/1 vector over TAXONOMY.capabilities, plus an unmapped set for
labels that are not in the taxonomy (never silently snapped). Union fusion
must be a componentwise superset of each parent, including unmapped extras.
"""
from __future__ import annotations

from typing import Any

TAXONOMY: dict[str, Any] = {
    "id": "foundry-capability-taxonomy",
    "version": "1.0.0",
    "capabilities": [
        "research.web",
        "research.cite",
        "review.adversarial",
        "review.schema",
        "build.emit",
        "build.test",
        "gate.confidence",
        "gate.budget",
        "security.scan",
        "ops.deploy",
    ],
}


def coverage_vector(workflow: dict, taxonomy: dict | None = None) -> dict:
    tax = taxonomy or TAXONOMY
    names: list[str] = list(tax["capabilities"])
    known = set(names)
    present: set[str] = set()
    unmapped: set[str] = set()
    for stage in workflow.get("stages") or []:
        for cap in stage.get("capabilities") or []:
            if cap in known:
                present.add(cap)
            else:
                unmapped.add(str(cap))
    return {
        "taxonomy_id": tax["id"],
        "taxonomy_version": tax["version"],
        "names": names,
        "vector": [1 if n in present else 0 for n in names],
        "unmapped": sorted(unmapped),
    }


def is_superset(union_cov: dict, parent_cov: dict) -> bool:
    uv = union_cov["vector"]
    pv = parent_cov["vector"]
    if len(uv) != len(pv):
        return False
    if any(u < p for u, p in zip(uv, pv)):
        return False
    return set(parent_cov.get("unmapped") or []) <= set(union_cov.get("unmapped") or [])


def missing_from_superset(union_cov: dict, parent_cov: dict) -> list[str]:
    names = parent_cov.get("names") or union_cov.get("names") or []
    missing: list[str] = []
    for i, (u, p) in enumerate(zip(union_cov["vector"], parent_cov["vector"])):
        if p and not u:
            missing.append(names[i] if i < len(names) else f"idx:{i}")
    for cap in parent_cov.get("unmapped") or []:
        if cap not in (union_cov.get("unmapped") or []):
            missing.append(cap)
    return missing
