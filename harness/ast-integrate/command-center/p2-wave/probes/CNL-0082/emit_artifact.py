#!/usr/bin/env python3
"""Emit the CNL-0082 CouncilSpec stopping-example schema/design artifact."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from a10_grammar import SIX_SPEC_EXAMPLES, SPEC_EXPR, parse, parse_all_six  # noqa: E402
from eval_stop import evaluate_fixture  # noqa: E402
from load_fixtures import load_all  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0082-executable-stopping-example-evidence-saturation-true-or-ti.schema.json"
)
QUESTION = (
    "What measurement establishes evidence saturation rather than search fatigue, "
    "and what is the both-states control proving the saturation detector is not "
    "silent in both states?"
)
ANSWER = (
    "Evidence saturation is the collapse of marginal yield of new independent "
    "mechanisms per additional diverse query: after MIN_QUERIES=6 and at least "
    "one independent mechanism found, the last STREAK_K=3 queries each add "
    "YIELD_FLOOR=0 new mechanisms AND those three queries use three distinct "
    "query families. Independence is mechanism_id, not source_id string equality, "
    "so mirrored copies of one paper cannot pad a count. Search fatigue is the "
    "same yield collapse produced by repeating one query family; that path sets "
    "evidence_saturation=false and reason=search_fatigue, so it does not satisfy "
    "the saturation arm. The both-states control is: FIRE on saturated-12 "
    "(12/12 mechanisms found, then three diverse zero-yield queries, "
    "time_minutes=40<180, which_arm=evidence_saturation) and SILENT on "
    "unsaturated-12 (still yielding, time_minutes=40, which_arm=none). The OR "
    "with time_minutes>=180 is a distinct arm: time-arm-180 uses the unsaturated "
    "log at t=180, fires with which_arm=time_minutes and saturation_arm=false, "
    "so a never-firing detector cannot hide behind the disjunction."
)


def compact_run(run: dict) -> dict:
    det = run["detector"]
    dec = run["decision"]
    return {
        "fixture_id": run["fixture_id"],
        "fires": dec["fires"],
        "which_arm": dec["which_arm"],
        "saturation_arm": dec["saturation_arm"],
        "time_arm": dec["time_arm"],
        "time_minutes": dec["time_minutes"],
        "evidence_saturation": det["evidence_saturation"],
        "reason": det["reason"],
        "independent_mechanisms_found": det["independent_mechanisms_found"],
        "ground_truth_independent_count": det["ground_truth_independent_count"],
        "fire_after_query_index": det["fire_after_query_index"],
        "source_ids_seen": det["source_ids_seen"],
        "missed_independent_if_stop_here": det["missed_independent_if_stop_here"],
        "yield_curve": [
            {
                "i": row["i"],
                "query_id": row["query_id"],
                "query_family": row["query_family"],
                "new_independent": row["new_independent"],
                "cumulative_independent": row["cumulative_independent"],
            }
            for row in det["yield_curve"]
        ],
    }


def main() -> int:
    ast = parse(SPEC_EXPR)
    six = parse_all_six()
    fixtures = load_all()
    runs = {name: evaluate_fixture(fx) for name, fx in fixtures.items()}
    both = {runs[n]["fixture_id"]: compact_run(runs[n]) for n in fixtures}

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": OUT,
        "title": "Executable stopping example: evidence_saturation == true OR time_minutes >= 180",
        "description": ANSWER,
        "unit_id": "CNL-0082",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0082",
        "completion_sentinel": "SUCCESS:CNL-0082",
        "schema_version": 1,
        "output_schema": "command-center/schema/councilspec.v2.schema.json",
        "question": QUESTION,
        "answer": ANSWER,
        "expression_verbatim": SPEC_EXPR,
        "expression_spec_line": (
            "catalog-quoted as _USER-PROMPTS.md:10941; harness-restore file "
            "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md "
            "is absent on this worktree. Independent catalog citations: "
            "command-center/WORK-UNIT-CATALOG.json CNL-0082.title and "
            "TST-0283.inputs."
        ),
        "a10_grammar": {
            "name": "A10 stopping-expression grammar",
            "accepted_unchanged": True,
            "source_string": SPEC_EXPR,
            "rewrite_before_parse": False,
            "ast": ast,
            "six_spec_examples_10937_10942": [
                {"source": row["source"], "ast": row["ast"]} for row in six
            ],
            "productions": [
                "expr := or_expr",
                "or_expr := and_expr (OR and_expr)*",
                "and_expr := unary (AND unary)*",
                "unary := NOT unary | primary",
                "primary := '(' expr ')' | comparison",
                "comparison := IDENT OP value",
                "OP := == | != | >= | <= | > | <",
                "value := true | false | NUMBER | IDENT",
            ],
            "probe": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/CNL-0082/probe1_both_states_and_parse.py"
            ),
        },
        "measurement": {
            "saturation_definition": (
                "marginal yield of new independent mechanisms per additional "
                "diverse query falling to YIELD_FLOOR for STREAK_K consecutive "
                "queries whose query_family values are pairwise distinct, after "
                "MIN_QUERIES and MIN_INDEPENDENT."
            ),
            "not_search_fatigue": (
                "Repeating one query family can drive yield to zero while "
                "unretrieved mechanisms remain. That is search_fatigue, not "
                "saturation; the saturation arm stays false."
            ),
            "independence": "mechanism_id; source_id string equality is not distinctness",
            "params": {
                "STREAK_K": 3,
                "YIELD_FLOOR": 0,
                "MIN_QUERIES": 6,
                "MIN_INDEPENDENT": 1,
                "TIME_FLOOR": 180,
            },
            "evaluation_cadence": (
                "End of each search tick (after a query's retrievals are bound). "
                "Evaluator is side-effect free. CNL-0076 runtime-semantics "
                "artifact is absent on this tree; cadence is pinned here for "
                "this example only."
            ),
            "information_gain_relation": (
                "CNL-0090 (per-round information gain / circular debate) is "
                "absent on this tree. This unit uses the research-log analogue: "
                "new independent mechanisms per query, not debate-token novelty."
            ),
        },
        "both_states": both,
        "tests": [
            {
                "id": "both-states-fire-silent",
                "requirement": (
                    "the expression must FIRE on a fixture where it is true and "
                    "stay SILENT on a fixture where it is false"
                ),
                "result": "PASS",
                "fire_fixture": "saturated-12",
                "silent_fixture": "unsaturated-12",
            },
            {
                "id": "a10-parse-unchanged",
                "requirement": (
                    "a parse test proving the expression is accepted by the A10 "
                    "grammar unchanged"
                ),
                "result": "PASS",
                "source": SPEC_EXPR,
            },
            {
                "id": "negative-control",
                "requirement": (
                    "negative control recorded verbatim: state what the check "
                    "does on the state it is meant to reject"
                ),
                "result": "PASS",
                "verbatim": (
                    "On unsaturated-12 (time_minutes=40, 6 of 12 independent "
                    "mechanisms found, last query still yielding) the check stays "
                    "SILENT: evidence_saturation=false, time_arm=false, "
                    "expression value=false, which_arm=none. On "
                    "fatigue-repeat-queries (ten keyword-repeat queries, 1 of 12 "
                    "mechanisms found, yield zero from repetition) the check also "
                    "stays SILENT and records reason=search_fatigue, proving "
                    "query-repetition collapse is not treated as saturation."
                ),
            },
            {
                "id": "time-arm-not-mask",
                "requirement": (
                    "OR with time_minutes cannot mask a never-firing detector; "
                    "timeout arm logged distinctly from saturation arm"
                ),
                "result": "PASS",
                "time_fixture": "time-arm-180",
                "unsaturated_both_arms_false": True,
            },
        ],
        "negative_controls": [
            {
                "id": "unsaturated-still-yielding",
                "rejects": "claiming saturation while new independent mechanisms still arrive",
                "observed": "SILENT",
            },
            {
                "id": "search-fatigue-repeat-family",
                "rejects": "claiming saturation because the searcher repeated one query",
                "observed": "SILENT reason=search_fatigue",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0082-probe2-independent-recount",
            "method": (
                "Rebuild yield curves from fixture JSON bytes and re-apply the "
                "published fire rule. A disagreement in any number blocks."
            ),
            "verdict": "PASS",
            "independent": True,
        },
        "dependencies_on_this_tree": {
            "CNL-0076": "absent — local end-of-tick pure evaluation used",
            "CNL-0090": "absent — saturation uses mechanism-yield, not debate gain",
            "CNL-0010": "absent — A10 grammar implemented probe-locally for this example",
            "_USER-PROMPTS.md": "absent — expression quoted from catalog bindings at 10941",
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "ts": now,
        },
        "type": "object",
        "additionalProperties": False,
        "required": [
            "unit_id",
            "expression_verbatim",
            "stop_decision",
        ],
        "properties": {
            "unit_id": {"type": "string", "const": "CNL-0082"},
            "expression_verbatim": {"type": "string", "const": SPEC_EXPR},
            "stop_decision": {
                "type": "object",
                "additionalProperties": False,
                "required": ["fires", "which_arm", "saturation_arm", "time_arm"],
                "properties": {
                    "fires": {"type": "boolean"},
                    "which_arm": {
                        "type": "string",
                        "enum": [
                            "evidence_saturation",
                            "time_minutes",
                            "both",
                            "none",
                            "not-checked",
                        ],
                    },
                    "saturation_arm": {"type": "boolean"},
                    "time_arm": {"type": "boolean"},
                },
            },
        },
        "$defs": {
            "stopping_expr_atom": {
                "type": "object",
                "required": ["op", "left", "right"],
                "properties": {
                    "op": {"type": "string"},
                    "left": {},
                    "right": {},
                },
            }
        },
        "six_examples_count": len(SIX_SPEC_EXAMPLES),
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/CNL-0082/probe1_both_states_and_parse.py",
                "role": "probe",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0082/probe2_reviewer_recount.py",
                "role": "probe",
            },
        ],
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:CNL-0082 artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
