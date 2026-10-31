"""Blueprint registry for product discovery / synthesis / requirements / ranking."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

BLUEPRINT_IDS = (
    "product-discovery",
    "user-research-synthesis",
    "requirements-mining-reconciliation",
    "roadmap-prioritization",
)


@dataclass
class BlueprintRecord:
    id: str
    title: str
    workflow: dict[str, Any]
    capability_vector: set[str]
    stopping_rules: list[str]
    preset: dict[str, Any] = field(default_factory=dict)
    handler: str = ""


def list_blueprints() -> list[BlueprintRecord]:
    return [
        BlueprintRecord(
            id="product-discovery",
            title="Product discovery",
            workflow={"id": "wf.product-discovery", "spec_version": "1.0.0"},
            capability_vector={"interview", "opportunity-map"},
            stopping_rules=["opportunity-map-complete"],
            preset={"name": "discovery"},
            handler="discovery",
        ),
        BlueprintRecord(
            id="user-research-synthesis",
            title="User-research synthesis",
            workflow={"id": "wf.user-research-synthesis", "spec_version": "1.0.0"},
            capability_vector={"theme-cluster", "quote-ledger"},
            stopping_rules=["themes-saturated"],
            preset={"name": "synthesis"},
            handler="synthesis",
        ),
        BlueprintRecord(
            id="requirements-mining-reconciliation",
            title="Requirements mining and reconciliation",
            workflow={"id": "wf.requirements-mining-reconciliation", "spec_version": "1.0.0"},
            capability_vector={"silent-drop-detect", "explicit-drop"},
            stopping_rules=["accounting-complete"],
            preset={"name": "requirements"},
            handler="requirements",
        ),
        BlueprintRecord(
            id="roadmap-prioritization",
            title="Roadmap prioritization",
            workflow={"id": "wf.roadmap-prioritization", "spec_version": "1.0.0"},
            capability_vector={"rice-rank"},
            stopping_rules=["ranking-complete"],
            preset={"name": "prioritize"},
            handler="prioritize",
        ),
    ]
