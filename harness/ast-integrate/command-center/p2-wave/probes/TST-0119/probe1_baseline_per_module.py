#!/usr/bin/env python3
"""Probe 1: live baseline survival score per module, not only in aggregate.

Re-runs the isolated campaign. An aggregate-only table is an overclaim.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from mutation.gate import GATED_MODULES  # noqa: E402
from mutation.runner import run_campaign  # noqa: E402
from mutation.tree import tree_fingerprint  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "TST-0119.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0119-probe1 {msg}")
    return 1


def main() -> int:
    campaign = run_campaign(REPO)
    per = campaign["per_module"]
    agg = campaign["aggregate"]
    iso = campaign["isolation"]

    if len(per) < 2:
        return fail(f"need >=2 module rows, got {list(per)}")
    if agg.get("survival_score") is None or agg.get("total", 0) < 6:
        return fail(f"aggregate too thin: {agg}")
    if not iso.get("live_tree_unchanged"):
        return fail("isolation: live tree changed")
    src = REPO / "command-center/p2-wave/probes/TST-0119/subjects"
    if tree_fingerprint(src) != iso["pre_sha256"]:
        return fail("live subject fingerprint drifted")

    for name in sorted(GATED_MODULES):
        row = per.get(name)
        if not isinstance(row, dict):
            return fail(f"gated module {name} missing")
        if row.get("total", 0) < 1:
            return fail(f"{name} has no applicable mutants")
        if row.get("survived") != 0:
            return fail(f"{name} has survivors {row.get('survivors')}")
        if row.get("survival_score") != 0:
            return fail(f"{name} survival_score={row.get('survival_score')}")

    helper = per.get("helper_util") or {}
    if helper.get("survived", 0) < 1:
        return fail("expected helper_util default-argument mutant to survive")
    surv = helper.get("survivors") or []
    if not any(s.get("operator") == "default-argument-change" for s in surv):
        return fail(f"helper survivors missing default-argument-change: {surv}")
    for s in surv:
        if not s.get("operator") or not s.get("location"):
            return fail(f"survivor missing operator/location: {s}")

    if not campaign["gate"]["pass"]:
        return fail(f"gate red on live campaign: {campaign['gate']}")

    # Aggregate 1/N hides helper 1/1. Per-module must disagree with a naive
    # "suite is green" reading of the aggregate kill rate.
    if agg["survived"] < 1:
        return fail("aggregate survived=0; the hiding-survivor precedent is absent")
    if agg["killed"] / agg["total"] == helper["survival_score"]:
        return fail("aggregate collapsed onto the helper row")

    published_ok = None
    if RECEIPT.is_file():
        rec = json.loads(RECEIPT.read_text(encoding="utf-8"))
        pub = ((rec.get("mutation_campaign") or {}).get("per_module")) or {}
        for name, row in per.items():
            pr = pub.get(name) or {}
            if pr.get("survived") != row.get("survived") or pr.get("total") != row.get("total"):
                return fail(
                    f"receipt per_module[{name}] drifted live={row.get('survived')}/{row.get('total')} "
                    f"pub={pr.get('survived')}/{pr.get('total')}"
                )
        published_ok = True

    payload = {
        "pass": True,
        "probe": "probe1-baseline-per-module",
        "unit_id": "TST-0119",
        "per_module": {
            name: {
                "total": row["total"],
                "killed": row["killed"],
                "survived": row["survived"],
                "survival_score": row["survival_score"],
                "gated": row["gated"],
                "survivors": [
                    {"operator": s["operator"], "location": s["location"]}
                    for s in row["survivors"]
                ],
            }
            for name, row in per.items()
        },
        "aggregate": {
            "total": agg["total"],
            "killed": agg["killed"],
            "survived": agg["survived"],
            "survival_score": agg["survival_score"],
        },
        "gate_pass": campaign["gate"]["pass"],
        "live_tree_unchanged": True,
        "published_table_recomputed": published_ok,
        "isolation": iso["method"],
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    print(
        f"modules={len(per)} aggregate={agg['survived']}/{agg['total']} "
        f"helper_survivors={helper.get('survived')} gate={campaign['gate']['pass']}"
    )
    print("SUCCESS:TST-0119-probe1 baseline per-module survival score")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
