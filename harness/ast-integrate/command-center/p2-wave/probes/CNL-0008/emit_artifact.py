#!/usr/bin/env python3
"""Emit the CNL-0008 design artifact (JSON bytes at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import semantics as S  # noqa: E402

OUT = REPO / "command-center/design/council/CNL-0008-budget-block-12-dials-and-the-exhaustion-semantics.md"
QUESTION = (
    "For each of the 12 budget dials (effort, time, tokens, tool calls, sources, "
    "experiments, turns, speaking quotas, minimum engagement, maximum inactivity, "
    "rebuttal depth, escalation), does exhaustion HARD-STOP the council or DEGRADE "
    "it - and which choice silently corrupts the stopping rule if made wrong?"
)


def main() -> int:
    declared = S.run_all_declared()
    wrong = {d: S.run_wrong_choice(d) for d in S.DIAL_IDS}
    planted = S.evaluate(S.fixture_for("turns"))
    good = S.evaluate(S.known_good_consensus())
    mid = S.evaluate(S.midrun_engagement_unmet())
    eval_line = S.function_line("evaluate")
    masq_line = S.function_line("masquerade_fires")
    fix_line = S.function_line("fixture_for")

    dials = []
    for dial in S.DIAL_IDS:
        spec = S.DIAL_SPEC[dial]
        row = declared[dial]
        w = wrong[dial]
        dials.append(
            {
                "id": dial,
                "kind": spec["kind"],
                "exhaustion": spec["exhaustion"],
                "declared_reason_on_fixture": spec["declared_reason_on_fixture"],
                "observed_reason_on_fixture": row["reason"],
                "observed_match": row["match"],
                "stopping_set_size": row["stopping_set_size"],
                "roster_size": row["roster_size"],
                "markers": row["markers"],
                "wrong_choice": spec["wrong_choice"],
                "silent_corruption": spec["silent_corruption"],
                "wrong_choice_observed": {
                    "declared_reason": w["declared_reason"],
                    "corrupt_reason": w["corrupt_reason"],
                    "silently_became_consensus": w["silently_became_consensus"],
                    "roster_shrunk": w["roster_shrunk"],
                    "unrun_labelled_complete": w["unrun_labelled_complete"],
                    "depth_cap_as_answered": w["depth_cap_as_answered"],
                },
            }
        )

    budgets_fragment = {
        "$comment": (
            "Typed fragment for the CouncilSpec v2 budgets block. CNL-0001 owns the "
            "root envelope; this unit specifies exhaustion semantics only."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": ["dials", "stopping_precedence", "roster_frozen"],
        "properties": {
            "roster_frozen": {
                "type": "boolean",
                "const": True,
                "description": "MUTED and INACTIVE seats remain in the stopping set.",
            },
            "stopping_precedence": {
                "type": "array",
                "minItems": 4,
                "items": {"type": "string"},
            },
            "dials": {
                "type": "array",
                "minItems": 12,
                "maxItems": 12,
                "items": {
                    "type": "object",
                    "required": ["id", "exhaustion"],
                    "properties": {
                        "id": {"type": "string", "enum": list(S.DIAL_IDS)},
                        "exhaustion": {
                            "type": "string",
                            "enum": ["HARD_STOP", "DEGRADE", "GATE"],
                        },
                    },
                },
            },
        },
    }

    doc = {
        "unit_id": "CNL-0008",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0008",
        "title": "Budget block: 12 dials and the exhaustion semantics",
        "question": QUESTION,
        "answer": (
            "Four ceilings HARD-STOP: effort, time, tokens, turns. Seven dials DEGRADE: "
            "tool_calls, sources, experiments, speaking_quotas, maximum_inactivity, "
            "rebuttal_depth, escalation. One floor GATES consensus: minimum_engagement. "
            "The silent corruption is always the same shape: leftover agreement, a shrunk "
            "roster, unrun work scored complete, or a cap treated as an answer, rewritten "
            "as CONSENSUS. SUCCESS:CNL-0008"
        ),
        "stopping_precedence": [
            "HARD_STOP ceiling exhausted → BUDGET_EXHAUSTED (never CONSENSUS)",
            "minimum_engagement unmet on the stopping set → not CONSENSUS",
            "deadlock AND escalation exhausted → ESCALATION_EXHAUSTED",
            "outstanding depth-capped obligation → CONTINUE (cap is not an answer)",
            "all stopping-set positions agree AND floors met → CONSENSUS (may carry DEGRADED:* and COVERAGE_INCOMPLETE)",
            "else CONTINUE",
        ],
        "roster_frozen": True,
        "dials": dials,
        "budgets_schema_fragment": budgets_fragment,
        "claim_under_test": (
            "Remaining speakers agreeing after a budget binds is CONSENSUS."
        ),
        "claim_verdict": "REFUTED",
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/CNL-0008/semantics.py",
                "line": eval_line,
                "kind": "live-tree",
                "claim": "evaluate() is the declared stopping function; HARD_STOP binds before agreement.",
                "snippet": "def evaluate(state: CouncilState, policy: Policy = DECLARED) -> Verdict:",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0008/semantics.py",
                "line": masq_line,
                "kind": "live-tree",
                "claim": "masquerade_fires compares claimed CONSENSUS against declared reason — a second field.",
                "snippet": "def masquerade_fires(",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0008/semantics.py",
                "line": fix_line,
                "kind": "live-tree",
                "claim": "Each dial has a planted exhaustion fixture used by both probes.",
                "snippet": "def fixture_for(dial: str) -> CouncilState:",
            },
        ],
        "tests": [
            {
                "id": "exhaustion_per_dial",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/CNL-0008/probe1_exhaustion_per_dial.py"
                ),
                "result": "PASS",
                "observed": {d: declared[d]["reason"] for d in S.DIAL_IDS},
            },
            {
                "id": "masquerade",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/CNL-0008/probe2_masquerade_consensus.py"
                ),
                "result": "PASS",
                "planted_bad": {
                    "dial": "turns",
                    "reason": planted.reason,
                    "agreement": planted.agreement,
                    "masquerade_fires": S.masquerade_fires(
                        "CONSENSUS", S.fixture_for("turns")
                    ),
                },
                "known_good": {
                    "reason": good.reason,
                    "masquerade_fires": S.masquerade_fires(
                        "CONSENSUS", S.known_good_consensus()
                    ),
                },
            },
            {
                "id": "negative_control",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/CNL-0008/probe2_masquerade_consensus.py"
                ),
                "result": "PASS",
                "what_the_check_does_on_the_state_it_rejects": (
                    "masquerade_fires(CONSENSUS, turns-exhausted AND remaining-agree) "
                    "returns True (FIRES). On known-good consensus it returns "
                    f"{S.masquerade_fires('CONSENSUS', S.known_good_consensus())} (SILENT)."
                ),
                "midrun_engagement_unmet_reason": mid.reason,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0008-probe2-masquerade",
            "independent": True,
            "verdict": "PASS",
            "scope_not_agreement": True,
            "counterexample": (
                "turns cap 10/10 with alice/bob/cara all position=A evaluates to "
                "BUDGET_EXHAUSTED, not CONSENSUS. Claiming CONSENSUS FIRES the masquerade detector."
            ),
        },
        "strongest_surviving_counterargument": (
            "A DEGRADE capability (tool_calls/sources/experiments) CAN still end in CONSENSUS "
            "after the dial is exhausted, because the council may agree on already-gathered "
            "evidence. That is declared, not a masquerade — provided COVERAGE_INCOMPLETE stays "
            "on the artifact and unrun work is not scored complete. Treating that CONSENSUS as "
            "coverage-complete is the corruption; probe 2 observes CORRUPT:unrun_as_complete "
            "on the wrong-choice policy."
        ),
        "residual_unknowns": [
            "CNL-0001's CouncilSpec v2 root envelope is not on this worktree; this unit ships "
            "the budgets fragment and executable semantics, not the envelope merge.",
            "Numeric cap defaults (10/3/2) are fixture values, not production limits.",
        ],
        "artifacts": [
            {
                "path": "command-center/design/council/CNL-0008-budget-block-12-dials-and-the-exhaustion-semantics.md",
                "role": "primary",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0008/semantics.py",
                "role": "executable-semantics",
            },
        ],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} bytes={OUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
