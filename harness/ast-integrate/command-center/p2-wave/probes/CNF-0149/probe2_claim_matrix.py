#!/usr/bin/env python3
"""Probe 2: checkout-mode claim matrix, both-states format, REACH-6 blob vs worktree."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from matrix import OUT_REL, measure  # noqa: E402
from scenario import UNIT  # noqa: E402

ART = REPO / OUT_REL


def main() -> int:
    live = measure()
    tests = live["tests_required"]
    claims = live["claims"]
    r6 = live["reach6"]
    inputs = live["inputs_on_disk"]

    if not tests["misformatted_fails_both_checkout_modes"]:
        print("FAILED:CNF-0149-probe2 misformatted file did not fail both modes")
        return 1
    if not tests["good_style_passes_both_checkout_modes"]:
        print("FAILED:CNF-0149-probe2 good file failed a checkout mode")
        return 1
    if claims["bad.py_style"]["holds_on_ci_blob"]:
        print("FAILED:CNF-0149-probe2 bad.py style held on blob (detector silent)")
        return 1
    if not claims["good.py_style"]["holds_on_ci_blob"]:
        print("FAILED:CNF-0149-probe2 good.py style failed on blob")
        return 1
    if not claims["good.py_lint"]["holds_under_both_checkout_modes"]:
        print("FAILED:CNF-0149-probe2 lint not stable across checkout modes")
        return 1
    if claims["register.md_hash_raw"]["holds_under_both_checkout_modes"]:
        print("FAILED:CNF-0149-probe2 raw hash held under autocrlf=true (no EOL signal)")
        print(json.dumps(claims["register.md_hash_raw"], indent=2))
        return 1
    if not claims["register.md_hash_lf"]["holds_under_both_checkout_modes"]:
        print("FAILED:CNF-0149-probe2 LF-normalised hash did not hold across modes")
        return 1
    if not tests["reach6_blob_matches_recorded"]:
        print("FAILED:CNF-0149-probe2 REACH-6 blob hash != recorded")
        return 1
    if not tests["reach6_autocrlf_true_worktree_raw_differs"]:
        print("FAILED:CNF-0149-probe2 REACH-6 worktree raw hash equals blob")
        print(json.dumps(r6["autocrlf_true"], indent=2))
        return 1
    if not r6["autocrlf_true"]["current_validate_py_matches_recorded"]:
        print("FAILED:CNF-0149-probe2 current LF-norm validate.py would not match blob")
        return 1
    if not r6["autocrlf_true"]["raw_worktree_gate_would_mismatch"]:
        print("FAILED:CNF-0149-probe2 raw-worktree gate would not mismatch")
        return 1

    checklist = inputs["RELEASE-CHECKLIST.md"]
    if checklist["present"] is True and checklist["verdict"] == "REFUTED-ABSENT":
        print("FAILED:CNF-0149-probe2 checklist present/absent contradiction")
        return 1
    if checklist["verdict"] == "REFUTED-ABSENT" and checklist["line_citation"] is not None:
        print("FAILED:CNF-0149-probe2 absent file has a line citation")
        return 1

    if not ART.is_file():
        print("FAILED:CNF-0149-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("reach6", {}).get("recorded_from_blob") != r6["recorded_from_blob"]:
        print("FAILED:CNF-0149-probe2 receipt REACH-6 recorded hash stale")
        return 1
    if f"SUCCESS:{UNIT}" not in json.dumps(doc):
        print("FAILED:CNF-0149-probe2 sentinel absent")
        return 1

    print(json.dumps(
        {
            "probe": "probe2-claim-matrix",
            "unit_id": UNIT,
            "misformatted_fails_both": tests["misformatted_fails_both_checkout_modes"],
            "raw_hash_cross_mode": claims["register.md_hash_raw"][
                "holds_under_both_checkout_modes"
            ],
            "lf_hash_cross_mode": claims["register.md_hash_lf"][
                "holds_under_both_checkout_modes"
            ],
            "reach6_blob": r6["recorded_from_blob"],
            "reach6_true_raw": r6["autocrlf_true"]["worktree_raw_sha256"],
            "checklist_verdict": checklist["verdict"],
            "pass": True,
        },
        sort_keys=True,
    ))
    print(
        f"SUCCESS:{UNIT}-probe2 both-states format, REACH-6 blob≠raw-worktree, "
        f"checklist {checklist['verdict']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
