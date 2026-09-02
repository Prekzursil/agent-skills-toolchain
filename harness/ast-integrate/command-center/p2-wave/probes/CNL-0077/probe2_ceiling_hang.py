#!/usr/bin/env python3
"""Probe 2: floor cannot run forever; validation rejects hang and bypass.

Catalog tests_required:
  * the floor must be provably unable to run forever - a floor with no
    ceiling is a hang
Independent reviewer recount: re-derive unmet floors from the fixture
JSON, not from the design note's prose. A disagreement blocks the unit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import floor as F  # noqa: E402

ART = HERE.parents[2] / "design/council/CNL-0077-minimum-deliberation-conditions-that-outrank-any-early-sto.md"


def load_fix(name: str) -> dict:
    return json.loads((HERE / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0077-probe2 {msg}")
    return 1


def payload(doc: dict) -> dict:
    rep = doc.get("report")
    return rep if isinstance(rep, dict) else doc


def main() -> int:
    zero = load_fix("min-rounds-zero")
    err_zero = F.validate_spec(zero["spec"])
    print(json.dumps({"fixture": zero["id"], "validation_errors": err_zero}, sort_keys=True))
    if "min_rounds-below-hard-lower" not in err_zero:
        return fail(f"min_rounds=0 not rejected {err_zero}")
    d_zero = F.evaluate(zero["spec"], zero["state"], True)
    if d_zero["reason"] != F.SPEC_INVALID:
        return fail("min_rounds=0 honoured at runtime")

    no_ceil = load_fix("no-ceiling")
    err_ceil = F.validate_spec(no_ceil["spec"])
    print(json.dumps({"fixture": no_ceil["id"], "validation_errors": err_ceil}, sort_keys=True))
    if "floor-with-no-ceiling" not in err_ceil:
        return fail(f"no-ceiling not rejected {err_ceil}")

    unsat = load_fix("unsatisfiable-briefs")
    err_unsat = F.validate_spec(unsat["spec"])
    print(json.dumps({"fixture": unsat["id"], "validation_errors": err_unsat}, sort_keys=True))
    if "min_independent_briefs-unsatisfiable" not in err_unsat:
        return fail(f"unsatisfiable briefs not rejected {err_unsat}")

    inverted = F.default_spec(min_rounds=8, max_rounds=3)
    err_inv = F.validate_spec(inverted)
    print(json.dumps({"fixture": "min-exceeds-max", "validation_errors": err_inv}, sort_keys=True))
    if "min_rounds-exceeds-ceiling" not in err_inv:
        return fail(f"min>max not rejected {err_inv}")

    bounded = F.default_spec(max_rounds=4, min_rounds=2)
    sim = F.simulate(bounded, F.never_meet_timeline(20, stop_true=True))
    print(
        json.dumps(
            {
                "sim": "never-meet-floors-stop-true",
                "terminated": sim["terminated"],
                "hung": sim["hung"],
                "reason": sim["reason"],
                "iterations": sim["iterations"],
                "max_rounds": 4,
            },
            sort_keys=True,
        )
    )
    if sim["hung"]:
        return fail("bounded sim hung")
    if not sim["terminated"]:
        return fail("bounded sim did not terminate")
    if sim["reason"] != F.FLOOR_UNMET_AT_CEILING:
        return fail(f"bounded reason={sim['reason']}")
    if sim["iterations"] != 4:
        return fail(f"bounded iterations={sim['iterations']} want=4")

    # Both-states hang control: raise the ceiling past the hang_guard so
    # CONTINUE never hits max_rounds. The hang detector MUST fire. A
    # detector silent in both states measures nothing.
    mutant = F.default_spec(max_rounds=10**6, min_rounds=2)
    hang = F.simulate(mutant, F.never_meet_timeline(20, stop_true=True), hang_guard=5)
    print(
        json.dumps(
            {
                "sim": "mutant-no-effective-ceiling",
                "terminated": hang["terminated"],
                "hung": hang["hung"],
                "iterations": hang["iterations"],
                "hang_guard": 5,
            },
            sort_keys=True,
        )
    )
    if not hang["hung"]:
        return fail("hang-detector silent on no-effective-ceiling mutant")
    if hang["terminated"]:
        return fail("mutant unexpectedly terminated inside hang_guard")

    # Independent recount from fixture bytes (not from design-note prose).
    floored = load_fix("satisfied-but-floored")
    recount = F.floors_unmet(floored["spec"], floored["state"])
    recount_ids = [x["id"] for x in recount]
    print(json.dumps({"reviewer_recount_unmet": recount_ids}, sort_keys=True))
    want = [
        "min_rounds",
        "min_independent_briefs",
        "min_evidence_items",
        "mandated_roles_spoken",
    ]
    if recount_ids != want:
        return fail(f"reviewer-recount-mismatch got={recount_ids} want={want}")

    live = F.evaluate(floored["spec"], floored["state"], True)
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        table = payload(doc).get("fixture_table") or []
        row = next((r for r in table if r.get("id") == "satisfied-but-floored"), None)
        if not isinstance(row, dict):
            return fail("artifact-missing-satisfied-but-floored-row")
        if row.get("unmet_ids") != recount_ids:
            return fail(
                f"artifact-recount-disagreement artifact={row.get('unmet_ids')} live={recount_ids}"
            )
        if row.get("reason") != live["reason"] or row.get("action") != live["action"]:
            return fail("artifact-action-disagreement")
        try:
            import schema_check as SC
        except ImportError:
            return fail("schema_check-unavailable")
        errs = SC.error_list(doc)
        if errs:
            print("schema-errors " + "; ".join(errs[:8]))
            return fail(f"artifact-schema-invalid n={len(errs)}")
        print("schema-validate=PASS")

    print(
        "NEGATIVE CONTROL (verbatim): on the hang state (no effective ceiling, "
        f"stop true, floors unmet, hang_guard=5) hung={hang['hung']} "
        f"terminated={hang['terminated']}. The check FIRES (hung=true). On the "
        f"bounded ceiling state hung={sim['hung']} reason={sim['reason']}."
    )
    print("SUCCESS:CNL-0077-probe2 ceiling hang-bound validation reviewer-recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
