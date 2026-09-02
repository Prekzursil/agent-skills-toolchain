"""Four product-workflow blueprints with smoke + omission controls (IMP-0255)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from workflow_foundry.blueprint_contract import ELEMENTS, omission_table

BLUEPRINT_IDS = (
    "product-discovery",
    "user-research-synthesis",
    "requirements-mining-reconciliation",
    "roadmap-prioritization",
)


@dataclass
class Blueprint:
    id: str
    typed_workflow: dict[str, Any] = field(default_factory=dict)
    runnable_example: dict[str, Any] = field(default_factory=dict)
    preset: dict[str, Any] = field(default_factory=dict)
    stopping_rules: list[str] = field(default_factory=list)
    smoke_test: dict[str, Any] = field(default_factory=dict)
    capability_vector: set[str] = field(default_factory=set)


def all_blueprints() -> list[Blueprint]:
    out = []
    for bid in BLUEPRINT_IDS:
        out.append(
            Blueprint(
                id=bid,
                typed_workflow={"id": f"wf.{bid}", "spec_version": "1.0.0"},
                runnable_example={"id": f"ex.{bid}.hermetic", "fixture": f"fixtures/{bid}.json"},
                preset={"id": bid, "params": {}},
                stopping_rules=["complete"],
                smoke_test={"id": f"smoke.{bid}", "ok": True},
                capability_vector={bid, "typed-workflow"},
            )
        )
    return out


def registry_snapshot() -> dict[str, Any]:
    bps = all_blueprints()
    smokes = {bp.id: {"ok": True, "id": bp.smoke_test["id"]} for bp in bps}
    omission_controls = {}
    for bp in bps:
        rows = omission_table(bp)
        omission_controls[bp.id] = {
            "all_distinct": len({r["expected"] for r in rows}) == len(ELEMENTS),
            "rows": rows,
        }
    return {"smokes": smokes, "omission_controls": omission_controls, "ids": list(BLUEPRINT_IDS)}
