#!/usr/bin/env python3
"""Probe 1: exhaustiveness by typed-universe enumeration (signal A).

Recomputes exclusive routing over the cartesian product. Does not trust the
artifact's copied counts. Requires 0 unrouted, 0 multiply-routed, default
taken by a real assignment, and per-branch source-fit quotes.

A truncated taken-map that drops the default must fail the exercised check —
a checker that still passes is inert.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from workflow_fusion.conditional_hybrid import route  # noqa: E402
from workflow_fusion.typed_predicate import typed_universe  # noqa: E402
import scenario as S  # noqa: E402
from hybrid_op import (  # noqa: E402
    agreement_exclusive_vs_first_match,
    analyze_fitness,
    enumerate_routing,
)

ART = REPO / "command-center/wfa/WFA-0104-fusion-conditional-hybrid.json"
UNIT = "WFA-0104"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    spec = S.good_spec()
    fitness = analyze_fitness(spec)
    if len(fitness) != 4:
        return fail(f"fitness rows {len(fitness)} want 4")
    for row in fitness:
        if not row.get("quote") or not row.get("served_classes"):
            return fail(f"fitness incomplete {row.get('branch_id')}")
        if row["is_default"]:
            if "summarize" not in row["residual_classes"]:
                return fail(f"default residual {row['residual_classes']}")
        else:
            if not set(row["predicate_classes"]) <= set(row["served_classes"]):
                return fail(f"unfit {row['branch_id']}")

    report = enumerate_routing(spec)
    universe = typed_universe(spec["input_type"])
    if len(universe) != 16:
        return fail(f"universe_size={len(universe)} want 4*2*2=16")
    if report.unrouted:
        return fail(f"unrouted={report.unrouted}")
    if report.multiply:
        return fail(f"multiply_routed={report.multiply}")
    if report.default_taken < 1:
        return fail("default declared but never taken")
    if any(v < 1 for v in report.taken.values()):
        return fail(f"unexercised branch {report.taken}")
    if not agreement_exclusive_vs_first_match(spec, report):
        return fail("exclusive vs first-match disagreement")

    # Independent of exclusive matching: first-match route to source_id.
    for owner in report.owners:
        src = route(spec, owner["env"])
        if src != owner["source_id"]:
            return fail(f"route={src} owner={owner}")

    default_env = next(o["env"] for o in report.owners if o["branch_id"] == "br.default")
    if default_env["task_class"] != "summarize":
        return fail(f"default witness class {default_env}")

    # Inert-checker control: drop default takens and require detection.
    starved = type(report)(
        taken={k: (0 if k == "br.default" else v) for k, v in report.taken.items()},
        unrouted=list(report.unrouted),
        multiply=list(report.multiply),
        owners=[o for o in report.owners if o["branch_id"] != "br.default"],
        default_id="br.default",
    )
    if starved.default_taken != 0:
        return fail("starved control did not zero default_taken")
    if starved.default_taken >= 1:
        return fail("inert default-exercised check")

    if not ART.is_file():
        return fail("fusion artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    blob = json.dumps(doc)
    if "SUCCESS:WFA-0104" not in blob:
        return fail("sentinel absent")
    if doc.get("kind") != "FusionResult":
        return fail(f"kind={doc.get('kind')}")
    ex = doc.get("exhaustiveness") or {}
    if ex.get("unrouted") != 0 or ex.get("multiply_routed") != 0:
        return fail(f"artifact exhaustiveness {ex}")
    if ex.get("universe_size") != 16:
        return fail(f"artifact universe {ex.get('universe_size')}")
    if ex.get("default_taken") != report.default_taken:
        return fail(
            f"artifact default_taken={ex.get('default_taken')} live={report.default_taken}"
        )
    if ex.get("taken") != report.taken:
        return fail(f"artifact taken={ex.get('taken')} live={report.taken}")
    if not doc.get("default_exercised"):
        return fail("artifact default_exercised false")
    art_branches = {b["id"]: b for b in doc.get("branches") or []}
    for br in spec["branches"]:
        rec = art_branches.get(br["id"])
        if rec is None:
            return fail(f"artifact missing branch {br['id']}")
        fit = rec.get("source_fit") or {}
        if not fit.get("quote"):
            return fail(f"artifact branch {br['id']} missing source_fit.quote")
        if rec.get("taken_count_enumeration") != report.taken[br["id"]]:
            return fail(f"artifact taken_count drift on {br['id']}")
        if rec.get("witness") is None:
            return fail(f"artifact branch {br['id']} missing witness")

    out = {
        "probe": "probe1-enumeration",
        "unit_id": UNIT,
        "pass": True,
        "universe_size": 16,
        "unrouted": 0,
        "multiply_routed": 0,
        "default_taken": report.default_taken,
        "taken": report.taken,
        "default_witness": default_env,
        "agreement_with_first_match": True,
        "fitness_rows": len(fitness),
        "starved_control_zeroed": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"unrouted=0 multiply=0 universe=16 default_taken={report.default_taken} "
        f"taken={report.taken}"
    )
    print("SUCCESS:WFA-0104-probe1 exhaustiveness by enumeration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
