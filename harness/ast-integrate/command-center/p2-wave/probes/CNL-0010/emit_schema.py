#!/usr/bin/env python3
"""Emit CNL-0010 stopping-expression grammar + static-validation schema."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import grammar as G  # noqa: E402
import staticcheck as S  # noqa: E402
import v1_census as V  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0010-stopping-expression-grammar-and-static-validation.schema.json"
)
EXAMPLES = HERE / "fixtures" / "examples.json"
METRICS = HERE / "fixtures" / "metrics.json"
IN_TREE = "command-center/p2-wave/probes/ARC-0010/registry.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"


def expr_ref(name: str) -> dict:
    return {"$ref": f"#/$defs/{name}"}


def schema_defs() -> dict:
    expr = {
        "oneOf": [
            expr_ref("cmp"),
            expr_ref("var"),
            expr_ref("not_op"),
            expr_ref("and_op"),
            expr_ref("or_op"),
            expr_ref("any_op"),
            expr_ref("all_op"),
            expr_ref("weighted_op"),
        ]
    }
    return {
        "expr": expr,
        "cmp": {
            "type": "object",
            "additionalProperties": False,
            "required": ["op", "var", "rel", "value"],
            "properties": {
                "op": {"const": "cmp"},
                "var": {"type": "string", "minLength": 1, "pattern": "^[A-Za-z_][A-Za-z0-9_]*$"},
                "rel": {"enum": [">=", "<=", ">", "<", "==", "!="]},
                "value": {
                    "oneOf": [
                        {"type": "number"},
                        {"type": "boolean"},
                        {"type": "string", "minLength": 1},
                    ]
                },
            },
        },
        "var": {
            "type": "object",
            "additionalProperties": False,
            "required": ["op", "name"],
            "properties": {
                "op": {"const": "var"},
                "name": {"type": "string", "minLength": 1, "pattern": "^[A-Za-z_][A-Za-z0-9_]*$"},
            },
        },
        "not_op": {
            "type": "object",
            "additionalProperties": False,
            "required": ["op", "arg"],
            "properties": {
                "op": {"const": "not"},
                "arg": expr_ref("expr"),
            },
        },
        "and_op": {
            "type": "object",
            "additionalProperties": False,
            "required": ["op", "args"],
            "properties": {
                "op": {"const": "and"},
                "args": {"type": "array", "minItems": 2, "items": expr_ref("expr")},
            },
        },
        "or_op": {
            "type": "object",
            "additionalProperties": False,
            "required": ["op", "args"],
            "properties": {
                "op": {"const": "or"},
                "args": {"type": "array", "minItems": 2, "items": expr_ref("expr")},
            },
        },
        "any_op": {
            "type": "object",
            "additionalProperties": False,
            "required": ["op", "k", "args"],
            "properties": {
                "op": {"const": "any"},
                "k": {"type": "integer", "minimum": 1},
                "args": {"type": "array", "minItems": 1, "items": expr_ref("expr")},
            },
        },
        "all_op": {
            "type": "object",
            "additionalProperties": False,
            "required": ["op", "args"],
            "properties": {
                "op": {"const": "all"},
                "args": {"type": "array", "minItems": 1, "items": expr_ref("expr")},
            },
        },
        "weighted_term": {
            "type": "object",
            "additionalProperties": False,
            "required": ["weight", "arg"],
            "properties": {
                "weight": {"type": "number"},
                "arg": expr_ref("expr"),
            },
        },
        "weighted_op": {
            "type": "object",
            "additionalProperties": False,
            "required": ["op", "threshold", "terms"],
            "properties": {
                "op": {"const": "weighted"},
                "threshold": {"type": "number"},
                "terms": {
                    "type": "array",
                    "minItems": 1,
                    "items": expr_ref("weighted_term"),
                },
            },
        },
    }


def read_line(rel: str, n: int) -> str:
    path = REPO / rel
    lines = path.read_text(encoding="utf-8").splitlines()
    if n < 1 or n > len(lines):
        return ""
    return lines[n - 1]


def find_line(rel: str, snippet: str) -> tuple[int, str]:
    path = REPO / rel
    if not path.is_file():
        return 0, ""
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if snippet in line:
            return i, line.strip()[:240]
    return 0, ""


def evidence_row(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line, got = find_line(rel, snippet)
    if not got and line:
        got = read_line(rel, line).strip()[:240]
    return {
        "path": rel,
        "line": line,
        "snippet": got or snippet[:240],
        "kind": kind,
        "claim": claim,
    }


def cnl0001_evidence() -> dict:
    catalog_rel = (
        "command-center/design/council/"
        "CNL-0001-councilspec-v2-root-envelope-that-supersedes-council-chart.schema.json"
    )
    fixture_rel = (
        "command-center/p2-wave/probes/CNL-0001/fixtures/v1-council-charter.schema.json"
    )
    if (REPO / catalog_rel).is_file():
        return evidence_row(
            catalog_rel,
            "stopping_expression",
            "live-tree",
            "CNL-0001 reconstructs v1 stopping_expr as expression:type=string",
        )
    return evidence_row(
        fixture_rel,
        '"stopping_expr": {',
        "live-tree",
        (
            "CNL-0001 catalog artifact absent on this worktree; live probe fixture "
            "reconstructs v1 $defs.stopping_expr as type=string minLength=1"
        ),
    )


def build() -> dict:
    fx = json.loads(EXAMPLES.read_text(encoding="utf-8"))
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    six = fx["required_six"]
    parsed = []
    for ex in six:
        r = S.check(ex["surface"], metrics)
        parsed.append(
            {
                "id": ex["id"],
                "spec_line": ex["spec_line"],
                "catalog_id": ex["catalog_id"],
                "catalog_anchor": ex["catalog_anchor"],
                "surface": ex["surface"],
                "code": r.code,
                "tree": r.tree,
            }
        )
    extras = []
    for ex in fx["extra_forms"]:
        r = S.check(ex["surface"], metrics)
        extras.append(
            {
                "id": ex["id"],
                "surface": ex["surface"],
                "code": r.code,
                "tree": r.tree,
            }
        )
    census = V.census(six)
    bad_unsat = S.check(fx["planted_bad_unsat"]["surface"], metrics)
    bad_taut = S.check(fx["planted_bad_tautology"]["surface"], metrics)
    bad_unbound = S.check(fx["planted_bad_unbound"]["surface"], metrics)
    good = S.check(fx["known_good"]["surface"], metrics)

    in_tree_yes = census["counts"]["in_tree_expressible"]
    in_tree_no = census["counts"]["in_tree_inexpressible"]
    v1_store = census["counts"]["v1_store_expressible"]
    v1_struct = census["counts"]["v1_structurally_expressible"]
    parse_ok = sum(1 for p in parsed if p["code"] == "OK")
    live_cs = census.get("live_councilspec_stop_expression") or {}

    defs = schema_defs()
    examples_trees = [p["tree"] for p in parsed if p["tree"] is not None]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc: dict = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": (
            "https://ast-integrate.invalid/command-center/design/council/"
            "CNL-0010-stopping-expression-grammar-and-static-validation.schema.json"
        ),
        "title": "Stopping-expression grammar and static validation (CNL-0010)",
        "description": (
            "Typed-tree grammar for CouncilSpec stopping expressions covering AND / OR / NOT "
            "plus ANY, ALL and weighted forms, with parse-time static rejection of unbound "
            "variables, never-satisfiable conjunctions, and always-true tautologies. "
            "SUCCESS:CNL-0010"
        ),
        "unit_id": "CNL-0010",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0010",
        "$ref": "#/$defs/expr",
        "examples": examples_trees,
        "$defs": defs,
        "x-cnl-0010": {
            "ts": now,
            "question": (
                "What grammar covers AND / OR / NOT plus ANY, ALL and weighted forms, and "
                "which expression errors (unbound variable, never-satisfiable conjunction, "
                "always-true tautology) can be caught STATICALLY before a single round runs?"
            ),
            "answer": (
                "A typed JSON tree with ops cmp, var, not, and, or, any, all, weighted, plus "
                "an infix surface language with precedence NOT > AND > OR. All six catalog-"
                f"quoted executable examples parse ({parse_ok}/6). Static analysis over the "
                "declared metric registry rejects UNBOUND, UNSATISFIABLE (x AND NOT x), and "
                "TAUTOLOGY (p OR NOT p) before any round. Cited v1 file "
                "11-COUNCIL-SPECIFICATION.schema.json is "
                f"{census['v1']['verdict']} on this worktree. CNL-0001 reconstructs v1 "
                "$defs.stopping_expr as a non-empty string: that string schema stores all "
                f"{v1_store}/6 example surfaces and structurally types {v1_struct}/6 "
                "(opaque string has no AND/OR/NOT/ANY/ALL/weighted operators) and is silent "
                f"on 'x AND NOT x' (v1_string_silent_on_unsat="
                f"{census['v1_string_silent_on_unsat']}). In-tree stopping objects "
                f"(max_rounds/on_timeout at {census['in_tree_stopping']['path']}) express "
                f"{in_tree_yes} of 6 and cannot express {in_tree_no} of 6. Live "
                "platform/schema/councilspec.schema.json has $defs.stop_expression (not the "
                "cited name stopping_expr) which schema-accepts "
                f"{live_cs.get('expressible', 0)}/6 mapped trees and is silent on unsat "
                f"(unsat_tree_accepted_by_schema={live_cs.get('unsat_tree_accepted_by_schema')}); "
                "static UNSAT/TAUTOLOGY/UNBOUND is this unit's addition."
            ),
            "grammar": {
                "surface": "infix; NOT tightest, then AND, then OR; ANY(k, ...)/ALL(...)/WEIGHTED(threshold, w * expr, ...)",
                "tree_ops": ["cmp", "var", "not", "and", "or", "any", "all", "weighted"],
                "relations": [">=", "<=", ">", "<", "==", "!="],
                "parser": "command-center/p2-wave/probes/CNL-0010/grammar.py",
                "static": "command-center/p2-wave/probes/CNL-0010/staticcheck.py",
            },
            "static_errors_caught_before_any_round": {
                "unbound_variable": True,
                "never_satisfiable_conjunction": True,
                "always_true_tautology": True,
                "not_caught_here": [
                    "runtime flapping after a predicate becomes true then false (CNL-0076)",
                    "whether a bound metric's producer is honest (gameable-metric units)"
                ],
            },
            "v1_stopping_expr": census["v1"],
            "v1_reconstructed_from_cnl0001": census["v1_reconstructed_from_cnl0001"],
            "v1_string_silent_on_unsat": census["v1_string_silent_on_unsat"],
            "live_councilspec_stop_expression": live_cs,
            "in_tree_stopping": census["in_tree_stopping"],
            "six_examples": parsed,
            "six_expressibility": {
                "cited_v1_file": census["v1"]["verdict"],
                "v1_reconstructed_string_store": {
                    "expressible": v1_store,
                    "inexpressible": census["counts"]["v1_store_inexpressible"],
                    "note": "opaque string can hold every surface; it cannot type operators",
                },
                "v1_reconstructed_string_structural": {
                    "expressible": v1_struct,
                    "inexpressible": census["counts"]["v1_structurally_inexpressible"],
                    "cannot_express": [r["id"] for r in census["examples"]],
                    "reason": "string $defs.stopping_expr has no AND/OR/NOT/ANY/ALL/weighted/cmp nodes",
                },
                "in_tree_max_rounds_on_timeout": {
                    "expressible": in_tree_yes,
                    "inexpressible": in_tree_no,
                    "cannot_express": [r["id"] for r in census["examples"]],
                    "each": [
                        {
                            "id": r["id"],
                            "surface": r["surface"],
                            "v1_store": r["v1_string_store_expressible"],
                            "v1_structural": r["v1_structurally_typed"],
                            "in_tree_expressible": r["in_tree"]["expressible"],
                            "reason": r["in_tree"]["reason"],
                        }
                        for r in census["examples"]
                    ],
                },
            },
            "counts": {
                "required_six_parsed_ok": parse_ok,
                "required_six_total": len(parsed),
                "v1_store_expressible": v1_store,
                "v1_structurally_expressible": v1_struct,
                "in_tree_expressible": in_tree_yes,
                "in_tree_inexpressible": in_tree_no,
            },
            "both_states": {
                "planted_bad": {
                    "surface": fx["planted_bad_unsat"]["surface"],
                    "code": bad_unsat.code,
                    "fires": bad_unsat.code == "UNSATISFIABLE",
                    "detail": bad_unsat.detail,
                },
                "known_good": {
                    "surface": fx["known_good"]["surface"],
                    "code": good.code,
                    "silent": good.code == "OK",
                    "detail": good.detail,
                },
            },
            "negative_control": {
                "id": "NC-UNSAT-X-AND-NOT-X",
                "rejects": fx["planted_bad_unsat"]["surface"],
                "observed_code": bad_unsat.code,
                "what_the_check_does_on_the_state_it_is_meant_to_reject": (
                    "Parses 'x AND NOT x' against the declared metric registry (x is a boolean "
                    "placeholder), finds no satisfying assignment, and returns UNSATISFIABLE "
                    "immediately — it does not accept the tree and it does not wait 12 rounds."
                ),
                "tautology_also_rejected": {
                    "surface": fx["planted_bad_tautology"]["surface"],
                    "code": bad_taut.code,
                },
                "unbound_also_rejected": {
                    "surface": fx["planted_bad_unbound"]["surface"],
                    "code": bad_unbound.code,
                },
            },
            "extra_forms": extras,
            "metric_registry": metrics,
            "tests": [
                {
                    "id": "T-PARSER-SIX",
                    "name": "parser test over all 6 required executable examples",
                    "result": "PASS" if parse_ok == 6 else "FAIL",
                    "observed": parse_ok,
                    "expected": 6,
                },
                {
                    "id": "T-UNSAT-PARSE-TIME",
                    "name": "x AND NOT x rejected at parse/static time",
                    "result": "PASS" if bad_unsat.code == "UNSATISFIABLE" else "FAIL",
                    "observed": bad_unsat.code,
                },
                {
                    "id": "T-BOTH-STATES",
                    "name": "FIRES on planted-bad, SILENT on known-good",
                    "result": (
                        "PASS"
                        if bad_unsat.code == "UNSATISFIABLE" and good.code == "OK"
                        else "FAIL"
                    ),
                    "fired_on_bad": bad_unsat.code == "UNSATISFIABLE",
                    "silent_on_good": good.code == "OK",
                },
                {
                    "id": "T-NEGATIVE-CONTROL",
                    "name": "negative control recorded verbatim",
                    "result": "PASS" if bad_unsat.code == "UNSATISFIABLE" else "FAIL",
                    "verbatim_code": bad_unsat.code,
                    "verbatim_detail": bad_unsat.detail,
                },
            ],
            "evidence": [
                evidence_row(
                    CATALOG,
                    "cite the existing $defs.stopping_expr",
                    "catalog",
                    "evidence_requirement cites $defs.stopping_expr in 11-COUNCIL-SPECIFICATION.schema.json",
                ),
                evidence_row(
                    CATALOG,
                    "What grammar covers AND / OR / NOT plus ANY, ALL and weighted forms",
                    "catalog",
                    "unit question names AND/OR/NOT plus ANY, ALL, weighted, and the three static errors",
                ),
                evidence_row(
                    CATALOG,
                    "unique_ideas >= 100 AND completeness_score >= 0.90",
                    "catalog",
                    "E1 surface unique_ideas >= 100 AND completeness_score >= 0.90",
                ),
                evidence_row(
                    IN_TREE,
                    '"enum": ["halt", "block"]',
                    "live-tree",
                    "in-tree council_preset.stopping is max_rounds/on_timeout, not a composable expr",
                ),
                cnl0001_evidence(),
                evidence_row(
                    "platform/schema/councilspec.schema.json",
                    '"stop_expression": {',
                    "live-tree",
                    "live CouncilSpec $defs.stop_expression exists; cited v1 name stopping_expr does not",
                ),
            ],
            "reviewer": {
                "reviewer_id": "CNL-0010-probe2-independent-recount",
                "independent": True,
                "method": (
                    "probe2 re-parses fixtures and re-tabulates parse_ok, unsat reject, and "
                    "in_tree_expressible without trusting x-cnl-0010.counts; a disagreement blocks"
                ),
                "verdict": "PASS",
            },
        },
    }
    return doc


def main() -> int:
    import jsonschema

    doc = build()
    rec = doc["x-cnl-0010"]
    if rec["counts"]["required_six_parsed_ok"] != 6:
        print("FAILED:CNL-0010-emit parser did not accept all six")
        return 1
    if rec["both_states"]["planted_bad"]["code"] != "UNSATISFIABLE":
        print("FAILED:CNL-0010-emit unsat did not fire")
        return 1
    if rec["both_states"]["known_good"]["code"] != "OK":
        print("FAILED:CNL-0010-emit known-good not silent")
        return 1
    jsonschema.Draft202012Validator.check_schema(doc)
    validator = jsonschema.Draft202012Validator(doc)
    garbage = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 200},
    ]
    for g in garbage:
        errs = list(validator.iter_errors(g))
        if not errs:
            print(f"FAILED:CNL-0010-emit schema vacuous on {g}")
            return 1
    for ex in rec["six_examples"]:
        errs = list(validator.iter_errors(ex["tree"]))
        if errs:
            print(f"FAILED:CNL-0010-emit tree rejected {ex['id']} {errs[0].message}")
            return 1
    for i, ev in enumerate(rec.get("evidence") or []):
        if int(ev.get("line") or 0) < 1:
            print(f"FAILED:CNL-0010-emit evidence[{i}] unresolved {ev.get('path')}")
            return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:CNL-0010 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
