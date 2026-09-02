"""Charter field → evaluator binding census."""
from __future__ import annotations

from typing import Any

CHARTER_FIELDS = (
    "objective",
    "risk_class",
    "desired_output",
    "consensus_intent",
    "required_outputs",
    "success_criteria",
)

KNOWN_METRICS = {
    "unique_ideas": "quota.unique_ideas",
    "completeness_score": "outcomes.completeness",
    "calibration": "calibration.report",
}


def binding_census(charter: dict[str, Any]) -> dict[str, Any]:
    bindings = []
    for field in CHARTER_FIELDS:
        bindings.append(
            {
                "field": field,
                "present": field in charter,
                "evaluator": f"charter.{field}",
            }
        )
    bound = []
    unbound = []
    unsatisfiable = []
    vacuous = []
    for row in charter.get("success_criteria") or []:
        metric = str(row.get("metric") or "")
        rec = {
            "metric_id": metric,
            "criterion_id": row.get("id"),
            "op": row.get("op"),
            "threshold": row.get("threshold"),
            "field": "success_criteria",
        }
        if metric in KNOWN_METRICS:
            rec["evaluator"] = KNOWN_METRICS[metric]
            bound.append(rec)
        else:
            rec["reason"] = f"no evaluator bound for metric {metric}"
            unbound.append(rec)
    all_bound = bool(bound) and not unbound and not unsatisfiable
    return {
        "bindings": bindings,
        "bound": bound,
        "unbound": unbound,
        "unsatisfiable": unsatisfiable,
        "vacuous": vacuous,
        "all_bound": all_bound,
        "field_count": len(CHARTER_FIELDS),
        "criterion_count": len(charter.get("success_criteria") or []),
        "runtime_metrics": sorted(KNOWN_METRICS),
        "gating_failures": list(unbound),
    }
