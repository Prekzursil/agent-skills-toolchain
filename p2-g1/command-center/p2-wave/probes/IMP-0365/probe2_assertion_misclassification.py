#!/usr/bin/env python3
"""IMP-0365 probe2: assertion-based classification misclassifies (reviewer).

The catalog negative control: classify the labelled set by the CLAIMANT's
assertion instead of source.type and show the misclassification on the same
fixture. Then prove the admission gate does NOT use the assertion: every
admission row carries classifier_input_field=source.type.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.evidence.standard import (  # noqa: E402
    admit_claim,
    classify_by_claimant_assertion,
    classify_source_type,
    load_labelled_claims,
    misclassification_report,
)

RECEIPT = REPO / "command-center/receipts/IMP-0365.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0365-probe2 {msg}")
    return 1


def main() -> int:
    claims = load_labelled_claims()
    report = misclassification_report(claims)
    if report["shows_misclassification"] is not True:
        return fail("no-misclassification-shown")
    if report["n_mismatch"] < 3:
        return fail(f"mismatch-too-few:{report['n_mismatch']}")
    for row in report["rows"]:
        if row["truth"] == "anecdote" and row["asserted"] == "executable-proof-only":
            break
    else:
        return fail("no-anecdote-asserted-executable-row")

    # The gate's rows must name source.type as the classifier input, so the
    # claimant's assertion can never admit an under-tier claim.
    exec_preset = {"floor": "executable-proof-only",
                   "classifier_input_field": "source.type"}
    for c in claims:
        rec = admit_claim(exec_preset, c)
        if rec["classifier_input_field"] != "source.type":
            return fail(f"{c['id']}:wrong-classifier-field")
        if rec["admitted"] is True:
            tier = rec["classified_tier"]
            if tier not in ("peer-reviewed-only", "executable-proof-only"):
                return fail(f"{c['id']}:admitted-with-low-tier:{tier}")

    print(json.dumps({
        "probe": "probe2-assertion-misclassification",
        "unit_id": "IMP-0365",
        "pass": True,
        "n": report["n"],
        "n_mismatch": report["n_mismatch"],
        "mismatch_ids": report["mismatch_ids"],
        "classifier_input_field": report["classifier_input_field"],
    }, sort_keys=True))
    print("SUCCESS:IMP-0365-probe2 assertion classifier misclassifies; gate uses source.type")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
