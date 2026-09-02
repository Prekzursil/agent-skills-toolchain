#!/usr/bin/env python3
"""Probe 2: planted behavior change in a 'pure refactor' is caught.

GOOD: equivalent rewrite produces a differential-testing argument that holds.
BAD: mutant that drops casefold mismatches on generated mixed-case inputs.
NAIVE: 'no functional change' without running inputs is rejected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract  # noqa: E402
import refactoring as R  # noqa: E402

OUT = HERE / "probe2-refactor-equivalence.raw.json"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:IMP-0240-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, sort_keys=True, default=str)[:2000])
    return 1


def main() -> int:
    registered = contract.register_all()
    if registered["rejected_count"] or "wf.engineering.refactoring" not in registered["accepted"]:
        return fail("blueprint-not-registered", registered)

    codes = []
    sample = json.loads(
        (HERE / "blueprints" / "wf.engineering.refactoring.json").read_text(encoding="utf-8")
    )
    for drop in contract.REQUIRED_ELEMENTS:
        row = contract.omission_control(sample, drop)
        if row["accepted"] or row["code"] != drop:
            return fail("omission-code-mismatch", row)
        codes.append(row["code"])
    if len(set(codes)) != 6:
        return fail("omission-codes-not-distinct", codes)

    corpus = R.generate_inputs(seed=240, n=24)
    good = R.equivalence_argument(
        R.normalize_v1, R.normalize_v2_equivalent, corpus, label="equivalent-rewrite"
    )
    good_gate = R.accept_refactor_claim(good)
    if not good["equivalent"] or not good_gate["ok"] or good_gate["fired"]:
        return fail("equivalent-rewrite-not-accepted", {"good": good, "gate": good_gate})

    mutant = R.equivalence_argument(
        R.normalize_v1, R.normalize_mutant_drops_casefold, corpus, label="planted-mutant"
    )
    mutant_gate = R.accept_refactor_claim(mutant)
    if mutant["equivalent"] or mutant["mismatch_count"] < 1:
        return fail("mutant-not-caught-by-differential", mutant)
    if mutant_gate["ok"] or not mutant_gate["fired"] or mutant_gate["reason"] != "behavior-change-caught":
        return fail("mutant-gate", mutant_gate)

    naive = R.naive_no_functional_change(declared=True)
    naive_gate = R.accept_refactor_claim(naive)
    if naive_gate["ok"] or not naive_gate["fired"] or naive_gate["reason"] != "bare-no-functional-change":
        return fail("naive-assertion-accepted", {"naive": naive, "gate": naive_gate})

    doc = {
        "pass": True,
        "probe": "probe2-refactor-equivalence",
        "unit_id": "IMP-0240",
        "input_count": good["input_count"],
        "generated": True,
        "equivalent_rewrite_holds": True,
        "mutant_mismatch_count": mutant["mismatch_count"],
        "mutant_caught": True,
        "naive_bare_assertion_rejected": True,
        "fired_on_bad": True,
        "silent_on_good": True,
        "omission_codes": codes,
        "method": "differential-testing",
        "bare_no_functional_change_accepted": False,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    print(
        "equivalent=True mutant_caught=True naive_rejected=True "
        f"mismatches={mutant['mismatch_count']} omissions={len(codes)}"
    )
    print("SUCCESS:IMP-0240-probe2 planted behavior change caught by differential testing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
