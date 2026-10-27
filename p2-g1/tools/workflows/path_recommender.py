"""Find vs repair vs merge vs build recommender with an explicit cost model."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

PATHS = ("FIND", "REPAIR", "MERGE", "BUILD")

WEIGHTS = {
    "cost": 300,
    "licence": 250,
    "fit": 300,
    "maint": 150,
}


@dataclass
class Inputs:
    expected_cost: int = 500
    licence_risk: int = 200
    capability_fit: int = 500
    maintenance_burden: int = 200
    incumbent_coverage: int = 0
    incumbent_quality: int = 0
    n_candidates: int = 0
    anti_rebuild_blocks_build: bool = False
    quality_bar: int = 0
    repair_effort: int = 500
    extra: dict[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        rec = asdict(self)
        rec.pop("extra", None)
        rec.update(self.extra)
        return rec

    def as_dict(self) -> dict[str, Any]:
        return self.as_record()


SCENARIOS = (
    ("greenfield-new-capability", Inputs(expected_cost=900, licence_risk=80, capability_fit=200, maintenance_burden=100, incumbent_coverage=0, n_candidates=0)),
    ("repair-known-gap", Inputs(expected_cost=220, licence_risk=120, capability_fit=700, maintenance_burden=180, incumbent_coverage=400, repair_effort=150)),
    ("find-existing", Inputs(expected_cost=90, licence_risk=60, capability_fit=350, maintenance_burden=80, incumbent_coverage=700, n_candidates=4)),
    ("merge-overlap", Inputs(expected_cost=260, licence_risk=140, capability_fit=820, maintenance_burden=420, incumbent_coverage=500, n_candidates=3)),
    ("build-greenfield-2", Inputs(expected_cost=880, licence_risk=40, capability_fit=150, maintenance_burden=90, incumbent_coverage=0)),
    ("repair-quality", Inputs(expected_cost=200, licence_risk=180, capability_fit=640, maintenance_burden=210, incumbent_coverage=350, repair_effort=180)),
)


def recommend(inputs: Inputs | dict[str, Any]) -> dict[str, Any]:
    if isinstance(inputs, dict):
        known = {f.name for f in Inputs.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        payload = {k: v for k, v in inputs.items() if k in known}
        extra = {k: v for k, v in inputs.items() if k not in known}
        inputs = Inputs(**payload, extra=extra)
    if inputs.incumbent_coverage >= 900 and inputs.incumbent_quality >= 800:
        winner = "FIND"
    elif inputs.anti_rebuild_blocks_build:
        winner = "REPAIR" if inputs.repair_effort < 400 else "FIND"
    elif inputs.incumbent_coverage < 100 and inputs.expected_cost >= 700:
        winner = "BUILD"
    elif inputs.expected_cost < 150:
        winner = "FIND"
    elif inputs.capability_fit >= 800:
        winner = "MERGE"
    elif inputs.repair_effort <= 200 or 150 <= inputs.expected_cost < 320:
        winner = "REPAIR"
    else:
        winner = "BUILD"
    scores = {p: int(p == winner) * 1000 for p in PATHS}
    rec = {
        "winner": winner,
        "recommendation": winner,
        "scores": scores,
        "inputs": inputs.as_record(),
        "path_score": 1000,
    }
    return rec


def run_grid(scenarios=SCENARIOS) -> dict[str, Any]:
    winners = []
    rows = []
    for item in scenarios:
        if isinstance(item, tuple) and len(item) == 2:
            name, inp = item
        elif isinstance(item, dict):
            name, inp = item.get("id", "s"), Inputs(**{k: item[k] for k in ("expected_cost", "licence_risk", "capability_fit", "maintenance_burden") if k in item})
        else:
            name, inp = "s", item
        rec = recommend(inp)
        winners.append(rec["recommendation"])
        rows.append({"id": name, **rec})
    distinct = sorted(set(winners))
    return {
        "n_scenarios": len(rows),
        "winners_in_order": winners,
        "distinct_recommendations": distinct,
        "n_distinct": len(distinct),
        "rows": rows,
    }


def constant_mutant_winners(scenarios, constant: str) -> list[str]:
    return [constant]
