#!/usr/bin/env python3
"""Named probe 1: each declared tier enforced on the labelled claim set.

Classifier input field is named on every admission row. An under-tier
fixture (blog citation under executable-proof-only) is refused and does
not appear on the binding decision.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.evidence.standard import (  # noqa: E402
    CLASSIFIER_INPUT_FIELD,
    DECLARED_FLOORS,
    UnderTierError,
    attach_claim,
    bind_decision,
    classification_pass,
    expected_admitted_ids,
    load_labelled_claims,
    preset_for,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0365-probe1 {msg}")
    return 1


def main() -> int:
    claims = load_labelled_claims()
    if len(claims) < 5:
        return fail(f"labelled set too small: {len(claims)}")

    matrix = {}
    all_named = True
    for floor in DECLARED_FLOORS:
        preset = preset_for(floor)
        decision = bind_decision(preset, claims)
        expected = expected_admitted_ids(floor, claims)
        if decision["supporting_claim_ids"] != expected:
            return fail(
                f"{floor}: admitted {decision['supporting_claim_ids']} != {expected}"
            )
        if decision["classifier_input_field"] != CLASSIFIER_INPUT_FIELD:
            return fail("decision did not name classifier_input_field")
        leaked = [
            cid
            for cid in decision["refused_claim_ids"]
            if cid in decision["supporting_claim_ids"]
        ]
        if leaked:
            return fail(f"{floor}: refused claims bound: {leaked}")
        if expected and not decision["binding"]:
            return fail(f"{floor}: admitted claims but decision not binding")
        if not expected and decision["binding"]:
            return fail(f"{floor}: empty admission still binding")
        for row in decision["admissions"]:
            if row.get("classifier_input_field") != CLASSIFIER_INPUT_FIELD:
                all_named = False
        matrix[floor] = {
            "admitted": decision["supporting_claim_ids"],
            "refused": decision["refused_claim_ids"],
            "binding": decision["binding"],
        }

    if not all_named:
        return fail("an admission row omitted classifier_input_field")

    exec_matrix = matrix["executable-proof-only"]
    if exec_matrix["admitted"] != ["C-EXEC"]:
        return fail(f"executable-proof-only admitted {exec_matrix['admitted']}")
    if "C-CITED" not in exec_matrix["refused"]:
        return fail("under-tier C-CITED was not refused")

    preset = preset_for("executable-proof-only")
    decision = bind_decision(preset, claims)
    try:
        attach_claim(decision, "C-CITED")
        return fail("under-tier C-CITED attached to a binding decision")
    except UnderTierError:
        pass

    admitted_pass = classification_pass(claims, preset=preset)
    admitted_rows = [r for r in admitted_pass if r["admitted"]]
    if not admitted_rows:
        return fail("classification pass admitted nobody under executable-proof-only")
    for row in admitted_rows:
        if row["classifier_input_field"] != "source.type":
            return fail("admitted claim missing named classifier input field")

    payload = {
        "probe": "probe1-tier-enforcement",
        "unit_id": "IMP-0365",
        "classifier_input_field": CLASSIFIER_INPUT_FIELD,
        "labelled_claim_ids": [c["id"] for c in claims],
        "matrix": matrix,
        "under_tier_fixture": "C-CITED",
        "under_tier_refused": True,
        "under_tier_not_bound": True,
        "classification_pass_admitted": [
            {
                "claim_id": r["claim_id"],
                "classifier_input_field": r["classifier_input_field"],
                "classifier_input_value": r["classifier_input_value"],
                "classified_tier": r["classified_tier"],
            }
            for r in admitted_rows
        ],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "classifier_input_field=source.type "
        f"exec_admitted={exec_matrix['admitted']} "
        "under_tier=C-CITED refused"
    )
    print("SUCCESS:IMP-0365-probe1 each tier enforced; under-tier fixture refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
