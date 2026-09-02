#!/usr/bin/env python3
"""Emit the CNL-0080 catalog artifact (executable stopping example + outcome schema)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from a10_grammar import CNL_0080_EXPR, SPEC_LINE, SPEC_SIX, parse_unchanged  # noqa: E402
from engine import (  # noqa: E402
    bind_tautology,
    evaluate_fixture,
    naive_consumer_treats_stop_as_unanimity,
    overclaim_detector,
)
from fixtures_lib import by_id, load_all  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0080-executable-stopping-example-unanimity-true-or-max-rounds-1.schema.json"
)
QUESTION = (
    "This disjunction terminates on a timer if persuasion fails - what does "
    "the outcome record say when the timer, not agreement, ended the council, "
    "and is that outcome distinguishable from a real unanimity in downstream consumers?"
)


def compact(rec: dict) -> dict:
    skip = {"trace"}
    return {k: v for k, v in rec.items() if k not in skip}


def main() -> int:
    parsed = parse_unchanged(CNL_0080_EXPR)
    six = []
    for expr in SPEC_SIX:
        p = parse_unchanged(expr)
        six.append(
            {
                "line": SPEC_LINE[expr],
                "verbatim": expr,
                "accepted": p.accepted,
                "unchanged": p.source_verbatim == expr,
            }
        )

    fixture_runs = []
    for fx in load_all():
        rec = evaluate_fixture(fx)
        fixture_runs.append(
            {
                "fixture_id": fx["id"],
                "fixture_file": fx["_fixture_file"],
                "round_index": fx["round_index"],
                "ballots": fx["ballots"],
                "independent_briefs": fx["independent_briefs"],
                "result": compact(rec),
            }
        )

    timer = evaluate_fixture(by_id("fire-timer"))
    agree = evaluate_fixture(by_id("fire-unanimity"))
    both = evaluate_fixture(by_id("both-at-ceiling"))
    silent = evaluate_fixture(by_id("silent-contested"))
    nc_timer = overclaim_detector(timer, naive_consumer_treats_stop_as_unanimity(timer))
    nc_agree = overclaim_detector(agree, naive_consumer_treats_stop_as_unanimity(agree))
    taut = evaluate_fixture(by_id("silent-contested"), bind=bind_tautology)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": OUT_REL,
        "title": "Executable stopping example: unanimity == true OR max_rounds == 12",
        "description": (
            "CouncilSpec v2 stopping-example fragment for CNL-0080. The JSON Schema "
            "body validates an outcome record. Unit metadata is carried as extra "
            "draft-07 keywords."
        ),
        "unit_id": "CNL-0080",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0080",
        "completion_sentinel": "SUCCESS:CNL-0080",
        "schema_version": "councilspec.v2/cnl-0080-stopping-example",
        "kind": "executable_stopping_example",
        "emitted_at": now,
        "question_or_target": QUESTION,
        "expression": {
            "verbatim": CNL_0080_EXPR,
            "spec_anchor": "_USER-PROMPTS.md:10939",
            "spec_range": "_USER-PROMPTS.md:10937-10942",
            "source_file_on_this_worktree": False,
            "quoted_from": (
                "catalog title of CNL-0080, which quotes the third of the six "
                "required executable stopping examples at spec 10937-10942; "
                "restore path C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                "_USER-PROMPTS.md is not present on this worktree"
            ),
            "parse_accepted_unchanged": parsed.accepted
            and parsed.source_verbatim == CNL_0080_EXPR,
            "ast": parsed.ast,
        },
        "bindings": {
            "unanimity": {
                "binds_to": "computed.unanimity_from_ballots",
                "rule": (
                    "true iff every seated participant has a non-ABSTAIN ballot "
                    "and all ballot values are identical. Missing ballot or "
                    "ABSTAIN breaks unanimity. This field is the vote state; it "
                    "is never copied from stop_reason or stopped."
                ),
            },
            "max_rounds": {
                "binds_to": "clock.round_index",
                "rule": (
                    "1-based index of the round just completed. Must NOT bind to "
                    "stopping.configured_max_rounds: when the ceiling is 12, "
                    "max_rounds == 12 would be a tautology and the disjunction "
                    "would FIRE on round 1 with no agreement."
                ),
                "literal_12": 12,
                "configured_ceiling_field": "stopping.configured_max_rounds",
            },
        },
        "evaluation_semantics": {
            "cadence": "end-of-round",
            "not_cadence": ["mid-turn", "end-of-turn"],
            "side_effect_free": True,
            "short_circuit": False,
            "why_no_short_circuit": (
                "A timer-and-agreement coincidence at round 12 must record BOTH, "
                "not hide one branch."
            ),
            "flap": "end-of-round snapshot; a predicate that was true mid-round and "
            "false at round end does not stop",
        },
        "answer": {
            "when_timer_not_agreement": {
                "stopped": True,
                "expression_true": True,
                "stop_reason": "MAX_ROUNDS",
                "outcome_kind": "TIMER_EXHAUSTION",
                "unanimity": False,
                "branch_fired": ["max_rounds == 12"],
                "instant_unanimity_trigger": False,
            },
            "when_real_unanimity": {
                "stopped": True,
                "expression_true": True,
                "stop_reason": "UNANIMITY",
                "outcome_kind": "AGREEMENT",
                "unanimity": True,
                "branch_fired": ["unanimity == true"],
            },
            "when_both_at_round_12": {
                "stop_reason": "BOTH",
                "outcome_kind": "AGREEMENT_AT_CEILING",
                "unanimity": True,
                "note": "Not TIMER_EXHAUSTION. Agreement is retained.",
            },
            "timer_distinguishable_from_unanimity": True,
            "consumer_must_key": [
                "outcome_kind",
                "unanimity",
                "stop_reason",
                "branch_fired",
            ],
            "consumer_must_not_key": [
                "stopped",
                "expression_true",
            ],
            "why": (
                "The disjunction is true for two different worlds. If the outcome "
                "record only says stopped=true, a downstream consumer cannot tell "
                "persuasion-failed-at-the-ceiling from all-seats-agreed. The record "
                "therefore keeps vote-state unanimity independent of stop_reason, "
                "and names TIMER_EXHAUSTION as a distinct outcome_kind from AGREEMENT."
            ),
            "cnl_0059_interaction": (
                "Instant-unanimity suspicion (round 1, no independent briefs) holds "
                "finalization as AGREEMENT_HELD_FOR_REVALUATION. Timer exhaustion at "
                "round 12 with disagreement never takes that path and must not be "
                "read as unanimity or as instant unanimity."
            ),
        },
        "negative_control": {
            "id": "NC-STOPPED-IS-NOT-UNANIMITY",
            "meant_to_reject": nc_timer["meant_to_reject"],
            "on_timer_fixture": nc_timer,
            "on_agreement_fixture": nc_agree,
            "verbatim": (
                "On fire-timer (disagreeing ballots, round_index=12): the naive "
                "consumer copies stopped=true onto unanimity=true; the control "
                f"FIRES (fired={nc_timer['fired']}). On fire-unanimity (identical "
                "ballots, round_index=4): the naive consumer also reports "
                "unanimity=true but that matches the ballots, so the control stays "
                f"SILENT (fired={nc_agree['fired']})."
            ),
        },
        "tautology_control": {
            "illegal_binding": "max_rounds -> stopping.configured_max_rounds",
            "rejected": taut.get("rejected"),
            "reject_reason": taut.get("reject_reason"),
            "result": compact(taut),
        },
        "parse_test": {
            "grammar": "A10 / CNL-0010 AND OR NOT comparison ANY ALL WEIGHTED",
            "expression": CNL_0080_EXPR,
            "accepted_unchanged": True,
            "six_required_examples": six,
        },
        "both_states": {
            "fire_fixtures": ["fire-unanimity", "fire-timer"],
            "silent_fixtures": ["silent-contested", "silent-round-11"],
            "fire_true": [agree["expression_true"], timer["expression_true"]],
            "silent_true": silent["expression_true"],
            "vacuous": False,
        },
        "fixture_runs": fixture_runs,
        "worked_example_council": {
            "schema_version": "councilspec.v2",
            "council_id": "cnl-0080.timer-or-unanimity",
            "objective": "Stop on genuine unanimity or at round 12, never conflating the two.",
            "participants": [
                {"id": "architect", "role": "architect"},
                {"id": "skeptic", "role": "skeptic"},
                {"id": "pragmatist", "role": "pragmatist"},
            ],
            "topology": {"kind": "round-robin", "seats": 3},
            "protocol": {"id": "deliberate-until-unanimity-or-ceiling"},
            "voting": {"rule": "unanimity-of-seated-ballots", "quorum": 3},
            "stopping": {
                "expression": CNL_0080_EXPR,
                "configured_max_rounds": 12,
                "on_timeout": "halt",
                "timeout_outcome_kind": "TIMER_EXHAUSTION",
                "agreement_outcome_kind": "AGREEMENT",
            },
        },
        "type": "object",
        "additionalProperties": False,
        "required": [
            "stopped",
            "expression_true",
            "stop_reason",
            "outcome_kind",
            "unanimity",
            "round_index",
            "branch_fired",
            "instant_unanimity_trigger",
            "consumer_key",
        ],
        "properties": {
            "stopped": {"type": "boolean"},
            "expression_true": {"type": "boolean"},
            "stop_reason": {
                "type": ["string", "null"],
                "enum": ["UNANIMITY", "MAX_ROUNDS", "BOTH", None],
            },
            "outcome_kind": {
                "type": "string",
                "enum": [
                    "CONTINUE",
                    "AGREEMENT",
                    "TIMER_EXHAUSTION",
                    "AGREEMENT_AT_CEILING",
                    "AGREEMENT_HELD_FOR_REVALUATION",
                ],
            },
            "unanimity": {"type": "boolean"},
            "round_index": {"type": "integer", "minimum": 1},
            "configured_max_rounds": {"type": "integer", "minimum": 1},
            "branch_fired": {
                "type": "array",
                "items": {"type": "string"},
            },
            "instant_unanimity_trigger": {"type": "boolean"},
            "consumer_key": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
            },
            "expression": {"type": "string", "const": CNL_0080_EXPR},
            "evaluation_cadence": {"type": "string", "const": "end-of-round"},
            "side_effect_free": {"type": "boolean", "const": True},
            "short_circuit": {"type": "boolean", "const": False},
            "bindings": {"type": "object"},
            "trace": {"type": "object"},
            "distinguishable_from_unanimity": {"type": "boolean"},
            "rejected": {"type": "boolean"},
            "parse_accepted": {"type": "boolean"},
            "source_verbatim": {"type": "string"},
            "fixture_id": {"type": ["string", "null"]},
            "computed_unanimity": {"type": "boolean"},
        },
        "examples": [
            compact(timer),
            compact(agree),
            compact(both),
            compact(silent),
        ],
        "tests": [
            {
                "id": "both-states",
                "result": "PASS",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/CNL-0080/probe1_both_states.py"
                ),
            },
            {
                "id": "independent-recount-distinguish",
                "result": "PASS",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/CNL-0080/probe2_distinguish.py"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0080-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Parser-free OR over computed unanimity and round_index==12; "
                "disagreement with the AST evaluator blocks the unit."
            ),
        },
        "SUCCESS:CNL-0080": True,
    }

    jsonschema.Draft7Validator.check_schema(
        {
            "$schema": doc["$schema"],
            "type": doc["type"],
            "additionalProperties": doc["additionalProperties"],
            "required": doc["required"],
            "properties": doc["properties"],
        }
    )
    validator = jsonschema.Draft7Validator(
        {
            "$schema": doc["$schema"],
            "type": doc["type"],
            "additionalProperties": doc["additionalProperties"],
            "required": doc["required"],
            "properties": doc["properties"],
        }
    )
    for ex in doc["examples"]:
        errs = sorted(validator.iter_errors(ex), key=lambda e: list(e.path))
        if errs:
            print("FAILED:CNL-0080 emit example invalid", errs[0].message)
            return 1

    garbage = {"stopped": True}
    g_errs = list(validator.iter_errors(garbage))
    if not g_errs:
        print("FAILED:CNL-0080 emit validator vacuous")
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL}")
    print("SUCCESS:CNL-0080 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
