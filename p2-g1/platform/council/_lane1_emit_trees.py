"""Emit the canonical stopping-expression tree for each lane-1 preset.

Why this exists: SEM-001 compares `stopping.source_expression` to
`stopping.expression` with EXACT dict equality, so a hand-typed tree that differs
from the parser's output by one key or one number type is an ERROR. Rather than
hand-type 17 trees, this prints the parser's own canonical output for pasting.

Run:  python platform/council/_lane1_emit_trees.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib")
)

from councilspec.expression import parse, unparse  # noqa: E402

# council_id -> human stopping rule (the HUMAN-STOP line that ships in each preset)
RULES = {
    "c-m01-micro-triage-2seat": "ANY[rounds_elapsed >= 1, confidence >= 0.7]",
    "c-m02-micro-go-nogo-3voice": "rounds_elapsed >= 2 AND objections_open == 0",
    "c-m03-micro-single-claim-adjudication": (
        "custom:claim_source_probe_present == true "
        "AND custom:claim_independent_verifier_present == true "
        "AND evidence_items >= 2"
    ),
    "c-m04-micro-second-opinion-crossvendor": (
        "all_participants_spoke == true AND custom:crossvendor_and_gate_passed == true"
    ),
    "c-m05-micro-premortem-solo-plus-critic": (
        "custom:tripwires_with_detectors >= 3 AND counterexamples_found >= 3"
    ),
    "c-m06-micro-assumption-check": "custom:assumptions_all_rated == true",
    "c-m07-micro-scope-guard": "custom:non_goals_all_checked == true",
    "c-m08-micro-cost-sanity": (
        "custom:reference_class_named == true AND sources_gathered >= 1"
    ),
    "c-m09-micro-security-smell": (
        "custom:hard_ban_list_walked == true AND evidence_items >= 1"
    ),
    "c-m10-micro-should-we-stop": "custom:floor_met_or_named == true",
    "c-s11-design-gate-5": "all_participants_spoke == true AND independent_positions >= 5",
    "c-s12-plan-gate-3-adversarial": (
        "custom:stage0_plan_lint_clean == true AND quality_gate == PASS "
        "AND independent_positions >= 3"
    ),
    "c-s13-council-4voice-classic": "rounds_elapsed >= 2 AND all_participants_spoke == true",
    "c-s14-critique-panel-rubric": (
        "custom:all_rubric_dimensions_scored == true AND all_participants_spoke == true"
    ),
    "c-s15-arch-review-board-5": (
        "(objections_open == 0 AND rounds_elapsed >= 2) OR proof_of_impossibility == true"
    ),
    "c-s16-peer-review-3-blind": (
        "independent_positions >= 3 AND custom:reviewer_comment_overlap < 0.6"
    ),
    "c-g73-general-purpose-auto-composed": (
        "custom:composition_rationale_published == true AND rounds_elapsed >= 2 "
        "AND (consensus >= 0.75 OR proof_of_impossibility == true)"
    ),
}


def main() -> int:
    for cid, text in RULES.items():
        tree = parse(text)
        back = unparse(tree)
        assert parse(back) == tree, cid
        print(f"### {cid}\n# HUMAN-STOP: {text}\n# unparse: {back}")
        print(json.dumps(tree, indent=2))
        print()
    print(f"SUCCESS:lane1-emit-trees {len(RULES)} expressions parsed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
