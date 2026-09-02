#!/usr/bin/env python3
"""Score marketplace vs lifecycle machinery for the single-owner PR-ONLY estate."""
from __future__ import annotations

from typing import Any

from lifecycle import (
    ITEM_SPEC,
    LIFECYCLE_CORE,
    NAMED_MARKETPLACE,
    broken_ops_if_absent,
    minimal_subset,
    walk_four,
)

CRITERION = (
    "REQUIRED iff at least one of {install, update, rollback, uninstall} fails "
    "(blocked or postcondition) when the item is absent from an otherwise complete "
    "single-owner PR-ONLY estate. DEAD-WEIGHT iff no such operation fails AND the "
    "item's purpose requires a second publisher, a public audience, or a community "
    "(second_party_required), which PR-ONLY plus a single owner makes unreachable. "
    "DEFERRABLE iff no such operation fails AND the purpose is still reachable "
    "locally (for example owner-key signatures beside the lockfile sha256 pin)."
)


def classify(item: str, broken: list[str]) -> str:
    spec = ITEM_SPEC[item]
    if broken:
        return "required"
    if spec["second_party_required"]:
        return "dead-weight"
    return "deferrable"


def score_item(item: str) -> dict[str, Any]:
    spec = ITEM_SPEC[item]
    broken = broken_ops_if_absent(item)
    klass = classify(item, broken)
    if klass == "required":
        application = (
            f"Absent, these operations fail: {broken}. Classification stands as required."
        )
    elif klass == "dead-weight":
        application = (
            "Absent, no lifecycle operation fails. Purpose requires a second party "
            "and is unreachable under PR-ONLY single-owner. Dead-weight stands."
        )
    else:
        application = (
            "Absent, no lifecycle operation fails. Purpose remains reachable locally "
            f"({spec.get('adjacent_property') or spec['purpose']}). Deferrable."
        )
    return {
        "id": item,
        "name": spec["name"],
        "group": spec["group"],
        "classification": klass,
        "second_party_required": bool(spec["second_party_required"]),
        "broken_ops_if_absent": broken,
        "necessity_operation": broken[0] if broken else None,
        "purpose": spec["purpose"],
        "criterion_application": application,
        "priced_as_public_marketplace": False,
    }


def compute() -> dict[str, Any]:
    named = [score_item(i) for i in NAMED_MARKETPLACE]
    core = [score_item(i) for i in LIFECYCLE_CORE]
    dead = [r for r in named if r["classification"] == "dead-weight"]
    defer = [r for r in named if r["classification"] == "deferrable"]
    req_named = [r for r in named if r["classification"] == "required"]
    walk = walk_four(minimal_subset())
    blocked = [r["op"] for r in walk if not r["ok"]]
    n = len(named)
    d = len(dead)
    return {
        "named": named,
        "lifecycle_core": core,
        "walk_minimal": walk,
        "headline": {
            "named_marketplace_count": n,
            "dead_weight_count": d,
            "deferrable_count": len(defer),
            "required_from_named_count": len(req_named),
            "dead_weight_fraction": {"numer": d, "denom": n},
            "lifecycle_core_count": len(LIFECYCLE_CORE),
            "ops_blocked_on_minimal_subset": len(blocked),
            "blocked_ops": blocked,
            "public_marketplace_priced": False,
            "error_band": {
                "kind": "exact-integer",
                "dead_weight_count": 0,
                "notes": (
                    "Counts are integers from a necessity walker; the reviewer "
                    "must re-derive dead_weight_count exactly (band 0)."
                ),
            },
            "smallest_subset_ids": list(LIFECYCLE_CORE),
        },
        "disagreement": None,
    }
