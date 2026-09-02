#!/usr/bin/env python3
"""Named probe 1: decision-versus-N curve published; N* and default compared.

Two mechanically different readings of the same fixtures:
  1. Independent prefix-majority in scenario.py (does not import aggregate_majority)
  2. tools.council.sensitivity.evaluate_question (production majority, no retune)

The receipt experiment rows must match both. A self-import of the module's
own curve is not a second signal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import scenario as S  # noqa: E402
from council.sensitivity import (  # noqa: E402
    DEFAULT_SEAT_COUNT,
    evaluate_question,
    load_question,
    public_row,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0367-probe1 {msg}")
    return 1


def check_one(label: str, path: Path, live_row: dict, receipt_row: dict) -> str | None:
    q = S.load_json(path)
    indep = S.independent_curve(q)
    stab = S.independent_stabilisation(indep)
    live_curve = live_row.get("curve") or []
    if [(p["n"], p["decision"]) for p in live_curve] != [
        (p["n"], p["decision"]) for p in indep
    ]:
        return (
            f"{label} module curve != independent majority "
            f"live={[ (p['n'], p['decision']) for p in live_curve ]} "
            f"indep={[ (p['n'], p['decision']) for p in indep ]}"
        )
    rec_curve = receipt_row.get("curve") or []
    if [(p["n"], p["decision"]) for p in rec_curve] != [
        (p["n"], p["decision"]) for p in indep
    ]:
        return f"{label} receipt curve != independent majority"
    if int(live_row["stabilisation_n"]) != int(stab["stabilisation_n"]):
        return (
            f"{label} live N*={live_row['stabilisation_n']} "
            f"indep={stab['stabilisation_n']}"
        )
    if int(receipt_row["stabilisation_n"]) != int(stab["stabilisation_n"]):
        return f"{label} receipt N* != independent"
    if live_row.get("stable_decision") != stab["stable_decision"]:
        return f"{label} stable_decision mismatch"
    if live_row.get("n_sensitive") is not bool(stab["n_sensitive"]):
        return f"{label} n_sensitive live={live_row.get('n_sensitive')} indep={stab['n_sensitive']}"
    if live_row.get("retuned") is True:
        return f"{label} production path retuned the curve"
    if receipt_row.get("retuned") is True:
        return f"{label} receipt claims retune"
    if "default_relation" not in live_row or "default_n" not in live_row:
        return f"{label} default comparison missing on live row"
    if receipt_row.get("default_relation") != live_row.get("default_relation"):
        return f"{label} receipt default_relation != live"
    if int(receipt_row.get("default_n")) != int(q["default_n"]):
        return f"{label} receipt default_n != fixture"
    return None


def main() -> int:
    if not S.MODULE.is_file():
        return fail("tools/council/sensitivity.py missing")
    doc = S.require_receipt()
    by_id = S.public_by_id(doc)
    if not by_id:
        return fail("receipt experiment.questions empty")

    fixtures = (
        ("Q-evidence-decisive", S.FIX_DECISIVE),
        ("Q-n-sensitive", S.FIX_NSENS),
        ("Q-default-below", S.FIX_BELOW),
    )
    live_rows = {}
    for qid, path in fixtures:
        live = evaluate_question(load_question(path), aggregator="majority", retune=False)
        row = public_row(live)
        live_rows[qid] = row
        if qid not in by_id:
            return fail(f"receipt missing question {qid}")
        err = check_one(qid, path, row, by_id[qid])
        if err:
            return fail(err)
        if not live.get("production_path"):
            return fail(f"{qid} not marked production_path")

    dec = live_rows["Q-evidence-decisive"]
    if dec["stabilisation_n"] != 1:
        return fail(f"evidence-decisive N*={dec['stabilisation_n']} want=1")
    if dec["n_sensitive"] is True:
        return fail("evidence-decisive marked n_sensitive")
    if dec["default_relation"] != "above":
        return fail(f"evidence-decisive default_relation={dec['default_relation']} want=above")
    if int(dec["default_n"]) != DEFAULT_SEAT_COUNT:
        return fail(f"evidence-decisive default_n={dec['default_n']} want={DEFAULT_SEAT_COUNT}")

    nsens = live_rows["Q-n-sensitive"]
    if nsens["n_sensitive"] is not True:
        return fail("alternating-vote fixture was not n_sensitive")
    if len(nsens.get("distinct_decisions") or []) < 2:
        return fail("n-sensitive curve collapsed to one decision (tuned?)")
    if nsens["retuned"] is True:
        return fail("n-sensitive production retuned")

    below = live_rows["Q-default-below"]
    if below["default_relation"] != "below":
        return fail(f"default-below relation={below['default_relation']} want=below")
    if below["default_would_emit_unstable_answer"] is not True:
        return fail("default-below did not flag unstable answer at configured N")
    if below["stabilisation_n"] != 5:
        return fail(f"default-below N*={below['stabilisation_n']} want=5")
    if below["default_decision"] != "ACCEPT" or below["stable_decision"] != "REJECT":
        return fail(
            f"default-below default={below['default_decision']} "
            f"stable={below['stable_decision']}"
        )

    exp = doc.get("experiment") or {}
    if exp.get("curve_published") is not True:
        return fail("receipt experiment.curve_published is not true")
    if int(exp.get("question_count") or 0) != 3:
        return fail(f"receipt question_count={exp.get('question_count')} want=3")

    print(
        json.dumps(
            {
                "probe": "probe1-decision-vs-n",
                "unit_id": "IMP-0367",
                "pass": True,
                "rows": {
                    qid: {
                        "stabilisation_n": live_rows[qid]["stabilisation_n"],
                        "default_relation": live_rows[qid]["default_relation"],
                        "n_sensitive": live_rows[qid]["n_sensitive"],
                        "curve": [
                            {"n": p["n"], "decision": p["decision"]}
                            for p in live_rows[qid]["curve"]
                        ],
                    }
                    for qid, _ in fixtures
                },
            },
            sort_keys=True,
        )
    )
    print(
        "N*_decisive="
        f"{dec['stabilisation_n']} relation={dec['default_relation']} "
        f"N*_nsens={nsens['stabilisation_n']} N*_below={below['stabilisation_n']} "
        f"below_relation={below['default_relation']}"
    )
    print("SUCCESS:IMP-0367-probe1 decision-versus-N curve published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
