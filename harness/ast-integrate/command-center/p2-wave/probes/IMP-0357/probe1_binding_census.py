#!/usr/bin/env python3
"""Probe 1: criterion-to-evaluator census over every charter field.

Catalog test: binding census over all charter fields, unbound criteria listed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council import charter as C  # noqa: E402

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
UID = "IMP-0357"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe1 {msg}")
    return 1


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def main() -> int:
    good = load("good.json")
    census = C.binding_census(good)
    fields_seen = {row["field"] for row in census["bindings"]}
    missing = [name for name in C.CHARTER_FIELDS if name not in fields_seen]
    unbound_ids = [row["metric_id"] for row in census["unbound"]]
    report = {
        "probe": "probe1-binding-census",
        "unit_id": UID,
        "all_bound": census["all_bound"],
        "field_count": census["field_count"],
        "criterion_count": census["criterion_count"],
        "unbound_count": len(census["unbound"]),
        "unsatisfiable_count": len(census["unsatisfiable"]),
        "vacuous_count": len(census["vacuous"]),
        "fields_seen": sorted(fields_seen),
        "missing_charter_fields": missing,
        "bound_metrics": sorted(
            {row["metric_id"] for row in census["bound"] if row.get("metric_id")}
        ),
        "runtime_metrics": census["runtime_metrics"],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(
        f"all_bound={census['all_bound']} fields={sorted(fields_seen)} "
        f"criteria={census['criterion_count']} unbound={len(census['unbound'])}"
    )

    if missing:
        return fail(f"census skipped charter fields {missing}")
    if not census["all_bound"]:
        return fail(f"good charter gating_failures={census['gating_failures']}")
    if census["criterion_count"] < 2:
        return fail("good charter must bind at least the two measurable criteria")
    for metric_id in ("unique_ideas", "completeness_score"):
        if metric_id not in report["bound_metrics"]:
            return fail(f"{metric_id} not bound")

    # Unbound criterion must be listed, not silently dropped.
    unbound_charter = load("unbindable.json")
    bad = C.binding_census(unbound_charter)
    listed = [
        row
        for row in bad["unbound"]
        if row.get("metric_id") == "world_peace" or "world_peace" in row.get("reason", "")
    ]
    print(
        json.dumps(
            {
                "unbindable_all_bound": bad["all_bound"],
                "unbindable_unbound_count": len(bad["unbound"]),
                "world_peace_listed": bool(listed),
                "unbound_reasons": [row["reason"] for row in bad["unbound"]],
            },
            sort_keys=True,
        )
    )
    if bad["all_bound"]:
        return fail("unbindable charter reported all_bound")
    if not listed:
        return fail("world_peace criterion was not listed in unbound[]")

    # Empty success_criteria is an unevaluable aspiration.
    empty = dict(good)
    empty["success_criteria"] = []
    empty_census = C.binding_census(empty)
    if empty_census["all_bound"]:
        return fail("empty success_criteria must not census as all_bound")
    empty_reasons = " ".join(row["reason"] for row in empty_census["unbound"])
    if "no success criteria" not in empty_reasons:
        return fail(f"empty criteria not diagnosed: {empty_reasons}")

    # Unknown extra field fail-closed.
    extra = dict(good)
    extra["aspiration"] = "be excellent"
    extra_census = C.binding_census(extra)
    extra_unbound = [row for row in extra_census["unbound"] if row["path"] == "aspiration"]
    if not extra_unbound:
        return fail("unknown field 'aspiration' was not listed unbound")

    # String-form AND criteria bind the same two metrics.
    as_text = dict(good)
    as_text["success_criteria"] = "unique_ideas >= 100 AND completeness_score >= 0.90"
    text_census = C.binding_census(as_text)
    if not text_census["all_bound"]:
        return fail(f"string AND criteria failed: {text_census['gating_failures']}")

    print("SUCCESS:IMP-0357-probe1 binding census over all charter fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
