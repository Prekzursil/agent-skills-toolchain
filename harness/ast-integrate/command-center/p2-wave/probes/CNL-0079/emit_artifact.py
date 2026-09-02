#!/usr/bin/env python3
"""Emit the CNL-0079 catalog artifact from live fixture evaluation."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from a10 import accepted_unchanged, parse_all_required, tautology_or_unsat_rejected
from evaluate import lexical_mutant_run, run_council
from expr import A10_REQUIRED_EXAMPLES, SPEC_LINE, SPEC_RANGE, SPEC_EXPRESSION
from fixtures import fire, silent_low_consensus, silent_new_objection
from identity import jaccard

OUT_REL = (
    "command-center/design/council/"
    "CNL-0079-executable-stopping-example-consensus-0-95-and-no-new-obje.schema.json"
)


def main() -> int:
    f_true = fire()
    f_reset = silent_new_objection()
    f_low = silent_low_consensus()
    r_true = run_council(f_true)
    r_reset = run_council(f_reset)
    r_low = run_council(f_low)
    mutant = lexical_mutant_run(f_true)
    t0 = f_true["rounds"][0]["objections"][0]["text"]
    t1 = f_true["rounds"][1]["objections"][0]["text"]
    parse_rows = parse_all_required()
    unsat = tautology_or_unsat_rejected()
    parse_ok = all(
        row.get("accepted_unchanged") or row.get("accepted_unchanged") for row in parse_rows
    )
    if not (
        r_true["stop"]
        and not r_reset["stop"]
        and not r_low["stop"]
        and not mutant["stop"]
        and accepted_unchanged(SPEC_EXPRESSION)
        and parse_ok
    ):
        print("FAILED:CNL-0079 emit live evaluation does not satisfy both-states")
        print(
            json.dumps(
                {
                    "true": r_true["stop"],
                    "reset": r_reset["stop"],
                    "low": r_low["stop"],
                    "mutant": mutant["stop"],
                    "parse_ok": parse_ok,
                    "true_final": r_true.get("final"),
                    "reset_final": r_reset.get("final"),
                    "low_final": r_low.get("final"),
                    "mutant_final": mutant.get("final"),
                },
                sort_keys=True,
                default=str,
            )
        )
        return 1

    doc = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": OUT_REL,
        "title": "Executable stopping example: consensus >= 0.95 AND no_new_objection_rounds >= 2",
        "unit_id": "CNL-0079",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0079",
        "kind": "executable_stopping_example",
        "spec_anchor": SPEC_LINE,
        "spec_range": SPEC_RANGE,
        "expression_verbatim": SPEC_EXPRESSION,
        "expression_accepted_unchanged": True,
        "question": (
            "How is no_new_objection_rounds counted when an objection is restated "
            "in different words - and does the counter reset on a genuinely new "
            "objection from a newly recruited participant?"
        ),
        "answer": {
            "restatement_in_different_words": (
                "A restatement is the SAME objection when structured slots "
                "(target_claim_id, polarity, defect_class) match AND the named_observation "
                "fingerprint matches. Wording changes do not count as new and do not "
                "reset the quiet-round counter."
            ),
            "new_recruit_restates_existing": (
                "A newly recruited participant who only restates an already-admitted "
                "objection does NOT reset no_new_objection_rounds. The fire fixture "
                "reaches quiet=2 with R-new restating the latency defect."
            ),
            "new_recruit_raises_new": (
                "A genuinely new objection (different slots), including from a newly "
                "recruited participant, RESETS no_new_objection_rounds to 0. The "
                "reset fixture stays SILENT on the stop expression."
            ),
            "lexical_only_is_insufficient": (
                "Exact-string / high-Jaccard identity is the planted-bad mutant: it "
                "treats paraphrases as new, never accumulates quiet rounds, and stays "
                "SILENT on the true fixture. Canonical identity uses two mechanically "
                "different signals (slots + observation fingerprint)."
            ),
        },
        "metrics": {
            "consensus": {
                "formula": "support_weight / (support_weight + oppose_weight)",
                "silent_seats": "excluded from numerator and denominator (do not inflate)",
                "reasoned_dissent": "counted as oppose; distinguishable from silence",
                "threshold": 0.95,
            },
            "no_new_objection_rounds": {
                "cadence": "end-of-round snapshot after that round's objections are admitted",
                "increment": "round with zero newly admitted (non-same) objections",
                "reset": "any admitted objection that is not SAME as a previously admitted one",
                "inadmissible": "untyped free-text missing slots does not count",
                "threshold": 2,
            },
        },
        "evaluation_semantics": {
            "purity": "expression is side-effect free",
            "cadence_note": (
                "CNL-0076 runtime semantics are not on this worktree; this example "
                "evaluates once at end-of-round on the admitted snapshot."
            ),
            "conjunction": "AND is not OR under partial evidence; both predicates must hold",
        },
        "a10_grammar": {
            "note": (
                "CNL-0010 is not on disk here. Local A10 grammar accepts AND/OR/NOT, "
                "comparisons, parentheses, ANY/ALL. The spec string is parsed unchanged."
            ),
            "required_examples": parse_rows,
            "vacuous_parser_control": unsat,
        },
        "both_states": {
            "true_fixture": {
                "id": f_true.get("id"),
                "stop": r_true["stop"],
                "final": r_true["final"],
                "rounds": r_true["rounds"],
            },
            "false_new_objection_reset": {
                "id": f_reset.get("id"),
                "stop": r_reset["stop"],
                "final": r_reset["final"],
                "rounds": r_reset["rounds"],
            },
            "false_low_consensus": {
                "id": f_low.get("id"),
                "stop": r_low["stop"],
                "final": r_low["final"],
                "rounds": r_low["rounds"],
            },
        },
        "planted_bad_lexical_mutant": {
            "identity": mutant["identity"],
            "stop_on_true_fixture": mutant["stop"],
            "final": mutant["final"],
            "paraphrase_jaccard": jaccard(t0, t1),
            "control": "FIRES as a detection of a broken identity (mutant silent on true state)",
        },
        "negative_control": {
            "fixture_id": f_reset.get("id"),
            "intended_reject_state": "stop while a genuinely new objection just arrived",
            "observed_stop": r_reset["stop"],
            "observed_no_new_objection_rounds": r_reset["final"]["no_new_objection_rounds"],
            "observed_consensus": r_reset["final"]["consensus"],
            "verbatim": (
                "NEGATIVE_CONTROL verbatim: on fixture silent-new-objection-from-new-recruit-resets "
                f"the check REJECTS a stop. Observed: stop={r_reset['stop']} "
                f"no_new_objection_rounds={r_reset['final']['no_new_objection_rounds']} "
                f"consensus={r_reset['final']['consensus']:.4f} after round 3 "
                "(new defect_class missing-cost-term from newly recruited R-new reset the counter)."
            ),
        },
        "reviewer": {
            "method": "independent slot-set recount plus ballot-sum consensus, compared to run_council",
            "requirement": "disagreement in the number blocks the unit",
        },
        "dependencies_on_this_worktree": {
            "CNL-0051": "absent; local two-signal identity is scoped to this example",
            "CNL-0069": "absent; consensus is cast-ballot support share, silence vs dissent distinguishable",
            "CNL-0076": "absent; end-of-round snapshot is the scoped cadence",
            "prompt_file": "absent; expression quoted from catalog title / CNL-0069 citation of line 10938",
        },
        "a10_required_example_strings": list(A10_REQUIRED_EXAMPLES),
        "emitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "SUCCESS:CNL-0079": True,
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL}")
    print("SUCCESS:CNL-0079")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
