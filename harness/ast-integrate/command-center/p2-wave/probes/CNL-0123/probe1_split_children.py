#!/usr/bin/env python3
"""Probe 1: split-children fixture produces DISAGREEMENT, not majority PASS.

Oracle A: scripted-participant replay of split / all-pass / missing-receipt.
Also independently recounts the parent tally.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fanin import CLAIM_NOT_RECEIPT, DISAGREEMENT, PASS  # noqa: E402
from simulate import run_all  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0123-council-of-councils-fan-in-simulation-including-the-disagr.md"
)


def main() -> int:
    sim = run_all()
    split = sim["split"]
    all_pass = sim["all_pass"]
    missing = sim["missing"]

    if sim["split_labels"] != ["PASS", "PASS", "REFUTED"]:
        print("FAILED:CNL-0123-probe1 split labels", sim["split_labels"])
        return 1
    if split["verdict"] != DISAGREEMENT:
        print("FAILED:CNL-0123-probe1 split parent", split["verdict"])
        return 1
    if split["majority_of_labels"] != PASS:
        print("FAILED:CNL-0123-probe1 majority_of_labels not PASS")
        return 1
    if split["verdict"] == split["majority_of_labels"]:
        print("FAILED:CNL-0123-probe1 parent took the majority label")
        return 1
    if sim["split_recount"] != split["tally"]:
        print("FAILED:CNL-0123-probe1 recount mismatch", sim["split_recount"], split["tally"])
        return 1
    if split["tally"].get("PASS") != 2 or split["tally"].get("REFUTED") != 1:
        print("FAILED:CNL-0123-probe1 tally", split["tally"])
        return 1
    if split["distinct_source_count"] != 3:
        print("FAILED:CNL-0123-probe1 distinct_source_count", split["distinct_source_count"])
        return 1
    minority_ids = [r["id"] for r in split["minority"]]
    if minority_ids != ["child-gamma"]:
        print("FAILED:CNL-0123-probe1 minority", minority_ids)
        return 1
    gamma = next(r for r in split["children"] if r["id"] == "child-gamma")
    if "vote-count-fan-in" not in (gamma.get("evidence_excerpt") or ""):
        print("FAILED:CNL-0123-probe1 gamma evidence not folded into parent")
        return 1

    if all_pass["verdict"] != PASS:
        print("FAILED:CNL-0123-probe1 all-pass parent", all_pass["verdict"])
        return 1
    if missing["verdict"] == PASS:
        print("FAILED:CNL-0123-probe1 missing-receipt was accepted as PASS")
        return 1
    gamma_m = next(r for r in missing["children"] if r["id"] == "child-gamma")
    if gamma_m["receipt_status"] != CLAIM_NOT_RECEIPT:
        print("FAILED:CNL-0123-probe1 missing gamma status", gamma_m["receipt_status"])
        return 1
    if gamma_m["claimed_verdict"] != PASS:
        print("FAILED:CNL-0123-probe1 missing gamma claimed_verdict")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0123-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNL-0123":
        print("FAILED:CNL-0123-probe1 unit_id")
        return 1
    if "SUCCESS:CNL-0123" not in json.dumps(doc):
        print("FAILED:CNL-0123-probe1 sentinel")
        return 1
    declared = doc.get("declared_outcome") or {}
    if declared.get("parent_verdict") != DISAGREEMENT:
        print("FAILED:CNL-0123-probe1 artifact declared_outcome", declared)
        return 1
    if declared.get("rejected_parent_verdict") != PASS:
        print("FAILED:CNL-0123-probe1 artifact did not reject majority PASS")
        return 1
    recorded = ((doc.get("simulation") or {}).get("split") or {}).get("parent_digest")
    if recorded != split["parent_digest"]:
        print("FAILED:CNL-0123-probe1 artifact split digest mismatch")
        return 1

    print(
        json.dumps(
            {
                "split_verdict": split["verdict"],
                "split_tally": split["tally"],
                "majority_of_labels": split["majority_of_labels"],
                "all_pass_verdict": all_pass["verdict"],
                "missing_verdict": missing["verdict"],
                "missing_gamma_receipt": gamma_m["receipt_status"],
                "split_digest": split["parent_digest"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNL-0123-probe1 split-children declared outcome")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
