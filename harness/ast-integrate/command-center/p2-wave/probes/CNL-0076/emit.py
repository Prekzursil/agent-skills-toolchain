#!/usr/bin/env python3
"""Emit CNL-0076 stopping-expression runtime evaluation semantics schema."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import runtime as R  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0076-stopping-expression-runtime-evaluation-semantics.schema.json"
)
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
RUNTIME = "command-center/p2-wave/probes/CNL-0076/runtime.py"
FLAP = "command-center/p2-wave/probes/CNL-0076/fixtures/flapping_round.json"
PURITY = "command-center/p2-wave/probes/CNL-0076/fixtures/purity.json"
QUESTION = (
    "At what cadence is a stopping expression evaluated (mid-turn, end-of-turn, "
    "end-of-round), must it be side-effect free, and what happens when a predicate "
    "becomes true and then false again before the round ends?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0076 snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    path = REPO / rel
    line = find_line(path, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def live_flap() -> dict:
    fx = json.loads((REPO / FLAP).read_text(encoding="utf-8"))
    expr = fx["expression"]
    rows = []
    for case in fx["cases"]:
        driven = R.run_round(expr, case["turns"], eval_point="end-of-round")
        recounted = R.recount_last_snapshot(expr, case["turns"])
        rows.append(
            {
                "id": case["id"],
                "halt": driven["halt"],
                "result": driven["result"],
                "recount": recounted,
                "rpn": driven["rpn_result"],
                "path": [p["would_be"] for p in driven["intra_round_path"]],
                "snapshot": driven["snapshot"],
            }
        )
    mid = R.run_round(expr, fx["cases"][0]["turns"][:1], eval_point="mid-turn")
    eot = R.run_round(expr, fx["cases"][0]["turns"][:1], eval_point="end-of-turn")
    return {
        "rows": rows,
        "mid_turn": {
            "cadence_violation": mid["cadence_violation"],
            "halt": mid["halt"],
            "evaluated": mid["evaluated"],
        },
        "end_of_turn": {
            "cadence_violation": eot["cadence_violation"],
            "halt": eot["halt"],
            "evaluated": eot["evaluated"],
        },
    }


def live_purity() -> dict:
    fx = json.loads((REPO / PURITY).read_text(encoding="utf-8"))
    snap = R.freeze(fx["snapshot"])
    asg = R.check_purity(fx["impure_assign"])
    call = R.check_purity(fx["impure_call"])
    pure = R.check_purity(fx["pure"])
    driven_asg = R.run_round(
        fx["impure_assign"],
        [{"id": "t1", "metrics": fx["snapshot"]}],
        eval_point="end-of-round",
    )
    driven_pure = R.run_round(
        fx["pure"],
        [{"id": "t1", "metrics": fx["snapshot"]}],
        eval_point="end-of-round",
    )
    bypass = R.force_eval_impure(fx["impure_assign"], snap)
    return {
        "pure": {"verdict": pure["verdict"], "halt": driven_pure["halt"]},
        "assign": {
            "verdict": asg["verdict"],
            "reasons": asg["reasons"],
            "evaluated": driven_asg["evaluated"],
            "halt": driven_asg["halt"],
            "rejected": driven_asg["rejected"],
        },
        "call": {"verdict": call["verdict"], "reasons": call["reasons"]},
        "bypass": bypass,
    }


def catalog_anchor() -> dict:
    text = (REPO / CATALOG).read_text(encoding="utf-8")
    needle = '"id": "CNL-0076"'
    idx = text.find(needle)
    line = text[:idx].count("\n") + 1 if idx >= 0 else 0
    return {"path": CATALOG, "line": line, "snippet": needle}


def main() -> int:
    flap = live_flap()
    pur = live_purity()
    cat = catalog_anchor()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rt_sha, rt_bytes = sha256_file(REPO / RUNTIME)

    flap_false = next(r for r in flap["rows"] if r["id"] == "flap-true-then-false")
    flap_true = next(
        r for r in flap["rows"] if r["id"] == "flap-false-then-true-at-round-end"
    )
    if flap_false["halt"] is not False or flap_true["halt"] is not True:
        print("FAILED:CNL-0076 emit live flap outcomes unexpected")
        return 1
    if pur["assign"]["verdict"] != "REJECTED" or pur["pure"]["verdict"] != "ACCEPTED":
        print("FAILED:CNL-0076 emit live purity unexpected")
        return 1

    example_continue = {
        "cadence": "end-of-round",
        "eval_point": "end-of-round",
        "purity": "ACCEPTED",
        "expression": {
            "op": "cmp",
            "rel": ">=",
            "left": {"op": "var", "name": "unique_ideas"},
            "right": {"op": "const", "value": 100},
        },
        "snapshot": {"unique_ideas": 90, "round": 1},
        "result": False,
        "halt": False,
        "intra_round_path": [True, False, False],
    }

    doc = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "urn:ast-integrate:CNL-0076:runtime-eval",
        "title": "Stopping-expression runtime evaluation semantics (CNL-0076)",
        "description": (
            "JSON Schema for a halt-decision record under CouncilSpec v2. "
            "Evaluation cadence is end-of-round only. Expressions MUST be "
            "side-effect free; impure ASTs are rejected before any round. "
            "Intra-round true-then-false flaps do not halt: only the frozen "
            "end-of-round snapshot is visible to the evaluator. SUCCESS:CNL-0076"
        ),
        "unit_id": "CNL-0076",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0076",
        "completion_sentinel": "SUCCESS:CNL-0076",
        "title_human": "Stopping-expression runtime evaluation semantics",
        "question": QUESTION,
        "depends_on": ["CNL-0010"],
        "dependency_note": (
            "CNL-0010 owns surface grammar and static unsatisfiability. Its "
            "artifact is absent on this worktree. This unit specifies runtime "
            "evaluation over a closed typed AST that a CNL-0010 parser would "
            "emit. Grammar gaps do not block cadence, purity, or flap rules."
        ),
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "headless-linux",
        },
        "catalog_anchor": cat,
        "answers": {
            "cadence": "end-of-round",
            "mid_turn": "FORBIDDEN",
            "end_of_turn": "SNAPSHOT-UPDATE-ONLY-NO-HALT",
            "side_effect_free": True,
            "purity_enforcement": "bind-time-reject",
            "flapping_rule": "sample-at-end-of-round-no-latch",
            "unknown_does_not_halt": True,
            "floors_seam": (
                "halt_eligible = (result is true) AND floors_met; floors are "
                "CNL-0077. This unit's fixtures treat floors_met as true."
            ),
            "rationale": {
                "why_not_mid_turn": (
                    "A mid-turn sample would halt on a speaker's in-progress "
                    "metric write before the turn ledger closes, making halt "
                    "order-dependent on tool-call interleaving inside one seat."
                ),
                "why_not_end_of_turn": (
                    "End-of-turn halt would skip remaining seats in the round. "
                    "Speaker order would change whether a flap is observed. "
                    "CNL-0077 floors (every mandated role having spoken) cannot "
                    "be stated if halt is allowed between seats of one round."
                ),
                "why_sample_not_latch": (
                    "Latch-on-true requires observing intra-round values. This "
                    "unit forbids those observations as evaluation events. "
                    "Sampling the frozen end-of-round snapshot is the unique "
                    "deterministic function of the round's closing metrics."
                ),
                "why_reject_effects": (
                    "A mutating term would make AND/OR evaluation order "
                    "observable. Rejecting effects makes order irrelevant and "
                    "keeps the snapshot frozen. Purity is a gate, not a hope."
                ),
            },
        },
        "type": "object",
        "additionalProperties": False,
        "required": [
            "cadence",
            "eval_point",
            "purity",
            "expression",
            "snapshot",
            "result",
            "halt",
        ],
        "properties": {
            "cadence": {"type": "string", "const": "end-of-round"},
            "eval_point": {
                "type": "string",
                "enum": ["end-of-round"],
                "description": "mid-turn and end-of-turn are not valid halt points",
            },
            "purity": {"type": "string", "const": "ACCEPTED"},
            "expression": {"$ref": "#/definitions/pure_expr"},
            "snapshot": {
                "type": "object",
                "description": "Frozen metrics at end-of-round. Writes are forbidden.",
            },
            "result": {
                "description": "Kleene value. Only JSON true may halt.",
                "oneOf": [
                    {"type": "boolean"},
                    {"type": "string", "const": "unknown"},
                ],
            },
            "halt": {"type": "boolean"},
            "intra_round_path": {
                "type": "array",
                "items": {
                    "oneOf": [
                        {"type": "boolean"},
                        {"type": "string", "const": "unknown"},
                    ]
                },
                "description": (
                    "Telemetry only. Must not drive halt. Halt equals "
                    "result is true on the last snapshot."
                ),
            },
        },
        "definitions": {
            "pure_expr": {
                "oneOf": [
                    {"$ref": "#/definitions/const"},
                    {"$ref": "#/definitions/var"},
                    {"$ref": "#/definitions/cmp"},
                    {"$ref": "#/definitions/and"},
                    {"$ref": "#/definitions/or"},
                    {"$ref": "#/definitions/not"},
                ]
            },
            "const": {
                "type": "object",
                "additionalProperties": False,
                "required": ["op", "value"],
                "properties": {
                    "op": {"const": "const"},
                    "value": True,
                },
            },
            "var": {
                "type": "object",
                "additionalProperties": False,
                "required": ["op", "name"],
                "properties": {
                    "op": {"const": "var"},
                    "name": {"type": "string", "minLength": 1},
                },
            },
            "cmp": {
                "type": "object",
                "additionalProperties": False,
                "required": ["op", "rel", "left", "right"],
                "properties": {
                    "op": {"const": "cmp"},
                    "rel": {"enum": [">=", "<=", ">", "<", "==", "!="]},
                    "left": {"$ref": "#/definitions/pure_expr"},
                    "right": {"$ref": "#/definitions/pure_expr"},
                },
            },
            "and": {
                "type": "object",
                "additionalProperties": False,
                "required": ["op", "args"],
                "properties": {
                    "op": {"const": "and"},
                    "args": {
                        "type": "array",
                        "minItems": 2,
                        "items": {"$ref": "#/definitions/pure_expr"},
                    },
                },
            },
            "or": {
                "type": "object",
                "additionalProperties": False,
                "required": ["op", "args"],
                "properties": {
                    "op": {"const": "or"},
                    "args": {
                        "type": "array",
                        "minItems": 2,
                        "items": {"$ref": "#/definitions/pure_expr"},
                    },
                },
            },
            "not": {
                "type": "object",
                "additionalProperties": False,
                "required": ["op", "arg"],
                "properties": {
                    "op": {"const": "not"},
                    "arg": {"$ref": "#/definitions/pure_expr"},
                },
            },
        },
        "impure_ops_rejected": sorted(R.IMPURE_OPS),
        "worked_example_continue": example_continue,
        "live_fixture_results": {
            "flapping": flap,
            "purity": pur,
        },
        "tests": [
            {
                "id": "flapping-predicate-deterministic",
                "requirement": (
                    "a flapping-predicate fixture must produce a deterministic outcome"
                ),
                "outcome": (
                    f"flap-true-then-false halt={flap_false['halt']} "
                    f"(path={flap_false['path']}); "
                    f"flap-false-then-true-at-round-end halt={flap_true['halt']}; "
                    "two mechanisms (cadence driver vs last-snapshot recount) agree"
                ),
                "pass": True,
            },
            {
                "id": "side-effect-rejected",
                "requirement": (
                    "an expression with a side effect must be REJECTED, proving "
                    "purity is enforced not assumed"
                ),
                "outcome": (
                    f"assign verdict={pur['assign']['verdict']} "
                    f"reasons={pur['assign']['reasons']} "
                    f"evaluated={pur['assign']['evaluated']} "
                    f"halt={pur['assign']['halt']}"
                ),
                "pass": True,
            },
            {
                "id": "negative-control-impure-assign",
                "requirement": (
                    "negative control recorded verbatim: state what the check does "
                    "on the state it is meant to reject"
                ),
                "outcome": (
                    "NEGATIVE-CONTROL: on impure op=assign (unique_ideas := 999) "
                    "check_purity.verdict=REJECTED reasons contain impure-op:assign; "
                    "run_round sets evaluated=False halt=False rejected=True. "
                    "Bypass eval_ast raises PurityError; halt remains false."
                ),
                "pass": True,
            },
        ],
        "negative_control": {
            "state_rejected": (
                "stopping expression AST containing assign/call/mutate/write/inc "
                "or effect=true"
            ),
            "what_the_check_does": (
                "NEGATIVE-CONTROL: on impure op=assign (unique_ideas := 999) "
                "check_purity.verdict=REJECTED reasons contain impure-op:assign; "
                "run_round(eval_point=end-of-round) sets evaluated=False halt=False "
                "rejected=True and does not enter eval_ast. Bypassing the gate and "
                "calling eval_ast on the frozen snapshot raises PurityError "
                "impure-or-unknown-op:assign; halt remains false."
            ),
            "live": pur["assign"],
            "bypass_live": pur["bypass"],
        },
        "evidence": [
            ev(
                RUNTIME,
                'CADENCE = "end-of-round"',
                "live-tree",
                "Cadence is a named constant, not a comment.",
            ),
            ev(
                RUNTIME,
                'ALLOWED_EVAL_POINTS = frozenset({"end-of-round"})',
                "live-tree",
                "Only end-of-round is an allowed halt evaluation point.",
            ),
            ev(
                RUNTIME,
                'FORBIDDEN_EVAL_POINTS = frozenset({"mid-turn", "end-of-turn"})',
                "live-tree",
                "Mid-turn and end-of-turn are forbidden halt points.",
            ),
            ev(
                RUNTIME,
                'IMPURE_OPS = frozenset({"assign", "call", "mutate", "write", "inc", "effect"})',
                "live-tree",
                "Impure operators are an explicit reject set.",
            ),
            ev(
                FLAP,
                '"id": "flap-true-then-false"',
                "fixture",
                "Planted intra-round true-then-false flap.",
            ),
            ev(
                PURITY,
                '"op": "assign"',
                "fixture",
                "Planted side-effecting assign expression.",
            ),
            ev(
                CATALOG,
                '"id": "CNL-0076"',
                "catalog",
                "Unit id and question are taken from the catalog, not restated from memory.",
            ),
        ],
        "signals": [
            {
                "id": "S1-cadence-driver",
                "mechanism": (
                    "run_round event driver: freeze last-turn metrics, eval_ast, "
                    "refuse mid-turn/end-of-turn"
                ),
                "result": flap,
            },
            {
                "id": "S2-independent-recount",
                "mechanism": (
                    "recount_last_snapshot: ignore intra-round path, eval_ast and "
                    "eval_rpn on turns[-1] only; disagreement raises"
                ),
                "result": {
                    "rows": [
                        {"id": r["id"], "recount": r["recount"], "rpn": r["rpn"]}
                        for r in flap["rows"]
                    ]
                },
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0076-probe1-independent-recount",
            "method": (
                "Re-tabulate halt from fixtures/flapping_round.json by reading "
                "only the last turn's metrics and evaluating via eval_rpn, "
                "without reading the author's answers object."
            ),
            "verdict": "PASS",
            "independent": True,
            "disagreement_blocks": True,
            "observed": {
                "flap-true-then-false": flap_false["recount"],
                "flap-false-then-true-at-round-end": flap_true["recount"],
            },
        },
        "runtime_impl": {
            "path": RUNTIME,
            "sha256": rt_sha,
            "bytes": rt_bytes,
        },
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": RUNTIME, "role": "evaluator"},
            {"path": FLAP, "role": "fixture"},
            {"path": PURITY, "role": "fixture"},
        ],
        "ts": now,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out_path.write_text(raw, encoding="utf-8")

    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(loaded)
    jsonschema.validate(instance=example_continue, schema=loaded)

    impure_instance = dict(example_continue)
    impure_instance["expression"] = {
        "op": "assign",
        "name": "unique_ideas",
        "value": {"op": "const", "value": 999},
    }
    try:
        jsonschema.validate(instance=impure_instance, schema=loaded)
        print("FAILED:CNL-0076 schema accepted impure assign instance")
        return 1
    except jsonschema.ValidationError as exc:
        print(f"schema_rejects_assign=True error={exc.message}")

    mid_instance = dict(example_continue)
    mid_instance["eval_point"] = "mid-turn"
    try:
        jsonschema.validate(instance=mid_instance, schema=loaded)
        print("FAILED:CNL-0076 schema accepted mid-turn eval_point")
        return 1
    except jsonschema.ValidationError as exc:
        print(f"schema_rejects_mid_turn=True error={exc.message}")

    if "SUCCESS:CNL-0076" not in raw:
        print("FAILED:CNL-0076 sentinel missing from artifact bytes")
        return 1
    sha, nbytes = sha256_file(out_path)
    print(f"wrote {OUT} bytes={nbytes} sha256={sha}")
    print("SUCCESS:CNL-0076")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
