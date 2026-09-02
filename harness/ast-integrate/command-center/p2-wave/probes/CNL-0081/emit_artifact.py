#!/usr/bin/env python3
"""Emit the CNL-0081 catalog artifact (JSON Schema + delivery metadata)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from a10_grammar import SPEC_SIX, THIS_EXPRESSION, accepted_unchanged, parse  # noqa: E402
from evaluate import decide  # noqa: E402
from fixtures import all_fixtures, write_fixture_files  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0081-executable-stopping-example-quality-gate-pass-and-unresolv.schema.json"
)
QUESTION = (
    "Who declares a counterexample load-bearing and who may declare it resolved "
    "- and what stops the same participant from doing both?"
)


def dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def parse_proof(expr: str) -> dict:
    node = accepted_unchanged(expr)
    return {
        "source": expr,
        "accepted": True,
        "source_unchanged": node.source_text == expr,
        "root_kind": node.kind,
        "root_op": node.op,
        "rewritten": False,
    }


def main() -> int:
    write_fixture_files()
    fixture_runs = []
    for st in all_fixtures():
        result = decide(st)
        if result["decision"] != st["expected_decision"]:
            print(
                f"FAILED:emit fixture {st['fixture_id']} "
                f"got {result['decision']} want {st['expected_decision']}"
            )
            return 1
        fixture_runs.append(
            {
                "fixture_id": st["fixture_id"],
                "expected": st["expected_decision"],
                "observed": result["decision"],
                "fired": result["fired"],
                "derived_unresolved": result["env"]["unresolved_load_bearing_counterexample"],
                "effective_quality_gate": result["env"]["quality_gate"],
                "claimed_unresolved": result["env"]["claimed_unresolved"],
                "claimed_mismatch": result["env"]["claimed_mismatch"],
                "negative_control": bool(st.get("negative_control")),
                "rejects": st.get("rejects"),
            }
        )

    six_parse = []
    for expr in SPEC_SIX:
        node = parse(expr)
        six_parse.append(
            {
                "expression": expr,
                "accepted": True,
                "source_unchanged": node.source_text == expr,
                "evaluated_in_this_unit": expr == THIS_EXPRESSION,
            }
        )

    fire = next(r for r in fixture_runs if r["fixture_id"] == "FIRE")
    silent = next(r for r in fixture_runs if r["fixture_id"] == "SILENT-unresolved")
    dual = next(r for r in fixture_runs if r["fixture_id"] == "NEG-dual-role")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "urn:p2:cnl-0081:stopping-example",
        "title": (
            "Executable stopping example: quality_gate == PASS AND "
            "unresolved_load_bearing_counterexample == 0"
        ),
        "unit_id": "CNL-0081",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0081",
        "completion_sentinel": "SUCCESS:CNL-0081",
        "emitted_at": now,
        "output_schema": "command-center/schema/councilspec.v2.schema.json",
        "question": QUESTION,
        "expression_verbatim": THIS_EXPRESSION,
        "source_citation": {
            "spec_block": "_USER-PROMPTS.md:10937-10942",
            "this_expression_line": 10940,
            "verbatim": THIS_EXPRESSION,
            "on_disk_in_this_worktree": False,
            "catalog_title_match": True,
            "note": (
                "The Windows restore path named in the catalog inputs is not on "
                "this Linux worktree. The expression is the catalog title of "
                "CNL-0081, which quotes that spec line. The six-example block "
                "is recorded as parse-only smoke in a10_parse.six_examples."
            ),
        },
        "answer": {
            "declares_load_bearing": (
                "LoadBearingRegistrar, a participant distinct from the "
                "counterexample author and from the claim author."
            ),
            "declares_resolved": (
                "ResolutionCertifier, a participant distinct from the author, "
                "the registrar who declared the record load-bearing, and the "
                "evidence producer who submitted the resolving bytes."
            ),
            "what_stops_same_participant_doing_both": (
                "A seat-incompatibility constraint evaluated every time the "
                "stopping expression is evaluated. If declared_load_bearing_by "
                "== resolved_by, seats_ok is false, the record remains in the "
                "derived unresolved count, and the AND stays SILENT. This is "
                "not a policy paragraph; it is the derived metric."
            ),
            "quality_gate_operator": (
                "QualityGateOperator may claim PASS only if they hold that "
                "role and are not the registrar of any load-bearing record in "
                "the same round. Claimed quality_gate is rewritten to FAIL "
                "when that constraint breaks."
            ),
            "derived_not_claimed": (
                "The integer field unresolved_load_bearing_counterexample on "
                "the state document is ignored. bind() always substitutes the "
                "derived count. A claimed 0 with an open or dual-seat record "
                "cannot FIRE."
            ),
        },
        "a10_parse": {
            "grammar_module": (
                "command-center/p2-wave/probes/CNL-0081/a10_grammar.py"
            ),
            "a10_means": (
                "CNL-0010 Stopping-expression grammar and STATIC validation. "
                "CNL-0010 is not delivered on this tree; this unit binds a "
                "local A10 surface sufficient to accept the spec examples "
                "unchanged (AND/OR/NOT, comparisons, identifiers, numbers, "
                "booleans). It does not claim to be the full CNL-0010 artifact."
            ),
            "this_expression": parse_proof(THIS_EXPRESSION),
            "six_examples": six_parse,
        },
        "evaluation_semantics": {
            "cadence": "end-of-round",
            "side_effect_free": True,
            "flapping": (
                "A predicate that is true then false before round-end does not "
                "FIRE. bind() is a pure function of the round-end state."
            ),
            "cnl_0076_note": (
                "CNL-0076 (runtime evaluation semantics) is a catalog "
                "dependency and is not delivered on this tree. Cadence is "
                "pinned locally so this example is executable without waiting "
                "on that circle."
            ),
        },
        "seat_incompatibility": {
            "roles": [
                "LoadBearingRegistrar",
                "ResolutionCertifier",
                "QualityGateOperator",
            ],
            "rules": [
                "author_id != declared_load_bearing_by",
                "declared_load_bearing_by holds LoadBearingRegistrar",
                "resolved_by != author_id",
                "resolved_by != declared_load_bearing_by",
                "resolved_by != evidence_producer_id",
                "resolved_by holds ResolutionCertifier",
                "quality_gate_operator_id holds QualityGateOperator",
                "quality_gate_operator_id is not declared_load_bearing_by on any load-bearing record",
            ],
            "fail_closed": True,
        },
        "both_states": {
            "fire": fire,
            "silent": silent,
            "note": (
                "FIRE is the fixture where the expression is true. SILENT is "
                "the fixture where it is false (open load-bearing "
                "counterexample). A detector silent in both states would fail "
                "this unit."
            ),
        },
        "negative_control": {
            "id": "NEG-dual-role",
            "state_it_rejects": (
                "quality_gate claimed PASS, unresolved claimed 0, one "
                "counterexample declared load-bearing and marked resolved, "
                "but declared_load_bearing_by == resolved_by."
            ),
            "what_the_check_does": (
                "seats_ok is false, derived unresolved stays 1, claimed 0 is "
                "ignored, decision is SILENT. The same participant cannot "
                "declare a counterexample load-bearing and then resolve it "
                "to satisfy the stop."
            ),
            "observed": dual,
        },
        "fixture_runs_verbatim": fixture_runs,
        "tests": {
            "both_states": {
                "fire_observed": fire["observed"],
                "silent_observed": silent["observed"],
                "pass": fire["observed"] == "FIRE" and silent["observed"] == "SILENT",
            },
            "a10_parse_unchanged": parse_proof(THIS_EXPRESSION)["source_unchanged"],
            "negative_control_silent": dual["observed"] == "SILENT",
        },
        "reviewer": {
            "reviewer_id": "CNL-0081-probe2-independent-recount",
            "method": (
                "Named probe2 re-tabulates unresolved count from fixture JSON "
                "with its own seat loop; it does not call evaluate.decide."
            ),
            "independent": True,
        },
        "type": "object",
        "additionalProperties": True,
        "required": [
            "quality_gate",
            "quality_gate_operator_id",
            "counterexamples",
            "roster",
        ],
        "properties": {
            "quality_gate": {"type": "string", "enum": ["PASS", "FAIL"]},
            "quality_gate_operator_id": {"type": "string", "minLength": 1},
            "unresolved_load_bearing_counterexample": {
                "type": "integer",
                "minimum": 0,
                "description": (
                    "Claimed count. The evaluator ignores this field and "
                    "substitutes the derived count from counterexamples."
                ),
            },
            "counterexamples": {
                "type": "array",
                "items": {"$ref": "#/definitions/counterexample_record"},
            },
            "roster": {"$ref": "#/definitions/roster"},
        },
        "definitions": {
            "counterexample_record": {
                "type": "object",
                "additionalProperties": True,
                "required": [
                    "id",
                    "author_id",
                    "declared_load_bearing",
                    "declared_load_bearing_by",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "claim_id": {"type": "string"},
                    "author_id": {"type": "string"},
                    "declared_load_bearing": {"type": "boolean"},
                    "declared_load_bearing_by": {"type": "string"},
                    "resolved": {"type": "boolean"},
                    "resolved_by": {"type": ["string", "null"]},
                    "evidence_producer_id": {"type": ["string", "null"]},
                    "resolving_evidence_ref": {"type": ["string", "null"]},
                },
            },
            "roster": {
                "type": "object",
                "required": ["participants"],
                "properties": {
                    "participants": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["id", "roles"],
                            "properties": {
                                "id": {"type": "string"},
                                "roles": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                        },
                    }
                },
            },
        },
        "dependencies_on_this_tree": {
            "CNL-0029": False,
            "CNL-0068": False,
            "CNL-0076": False,
            "CNL-0010": False,
            "note": (
                "Catalog dependencies are not delivered on this worktree. "
                "Seat incompatibility (CNL-0029), evidence-over-popularity "
                "(CNL-0068), evaluation cadence (CNL-0076), and the A10 "
                "grammar (CNL-0010) are implemented locally for THIS example "
                "so the unit is executable rather than parked. This is not a "
                "delivery of those units."
            ),
        },
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dump(doc), encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
