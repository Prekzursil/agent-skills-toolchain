#!/usr/bin/env python3
"""Emit the CNL-0083 design artifact (executable stopping example)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import a10_grammar as G  # noqa: E402
import evaluate as E  # noqa: E402
from record import independent_recount  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0083-executable-stopping-example-proof-of-impossibility-true.schema.json"
)
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
RHS = 7
QUESTION = (
    "What must be on disk for this single-term expression to evaluate true, "
    "and what is the negative control proving it cannot be satisfied by an "
    "unsuccessful search?"
)
NEGATIVE_CONTROL = (
    "On the unsuccessful-search fixture (visited {0,1} of S={0,1,2,3}), "
    "proof_of_impossibility == true evaluates False because coverage 2/4 "
    "is incomplete; the stop does not fire. 'We searched and did not find it' "
    "is not recorded as 'it cannot be found'."
)


PROOF_RECORD_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "command-center/design/council/CNL-0083-proof-of-impossibility-record.schema.json",
    "title": "ProofOfImpossibilityRecord",
    "type": "object",
    "additionalProperties": True,
    "required": [
        "claim",
        "predicate",
        "search_space",
        "methods",
        "resource_limit",
        "refuting_observation",
    ],
    "properties": {
        "claim": {"type": "string", "minLength": 8},
        "predicate": {
            "type": "object",
            "required": ["kind", "rhs"],
            "properties": {
                "kind": {"type": "string", "minLength": 1},
                "rhs": {"type": ["integer", "number"]},
            },
        },
        "search_space": {
            "type": "object",
            "required": ["kind", "members"],
            "properties": {
                "id": {"type": "string"},
                "kind": {"const": "finite-closed-set"},
                "element_type": {"type": "string"},
                "members": {"type": "array", "minItems": 1},
            },
        },
        "methods": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["name", "output"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "output": {"type": "string", "minLength": 1},
                },
            },
        },
        "resource_limit": {
            "type": "object",
            "required": ["status"],
            "properties": {
                "kind": {"type": "string"},
                "max_members": {"type": "integer"},
                "space_exhausted_before_limit": {"type": "boolean"},
                "status": {"type": "string", "minLength": 1},
            },
        },
        "refuting_observation": {
            "type": "object",
            "required": ["description", "observable_in_search_space"],
            "properties": {
                "description": {"type": "string", "minLength": 8},
                "observable_in_search_space": {"type": "boolean"},
                "would_appear_as": {"type": "string"},
                "circular": {"type": "boolean"},
            },
        },
    },
}


def catalog_anchor() -> dict:
    text = (REPO / CATALOG).read_text(encoding="utf-8")
    needle = '"title": "Executable stopping example: proof_of_impossibility == true"'
    idx = text.find(needle)
    line = text[:idx].count("\n") + 1 if idx >= 0 else 0
    return {
        "path": CATALOG,
        "line": line,
        "snippet": needle.strip('"'),
        "note": (
            "Windows source C:/Users/Prekzursil/.claude/harness-restore-20260806/"
            "_USER-PROMPTS.md:10937-10942 is not on this Linux worktree. The six "
            "required expressions are reconstructed from sibling CNL-0078..CNL-0083 "
            "catalog titles, which quote that range. Line 10942 is this unit's "
            "single-term expression."
        ),
    }


def compact(row: dict) -> dict:
    v = row["verdict"]
    return {
        "dir": row["dir"],
        "fires": row["fires"],
        "silent": row["silent"],
        "value": row["value"],
        "reason": v["reason"],
        "coverage": v.get("coverage"),
        "cardinality": v.get("cardinality"),
        "unseen": v.get("unseen"),
        "on_disk": row["on_disk"],
        "verbatim": (
            f"expression={row['expression']!r} value={row['value']!r} "
            f"fires={row['fires']} silent={row['silent']} reason={v['reason']} "
            f"coverage={v.get('coverage')}/{v.get('cardinality')}"
        ),
    }


def main() -> int:
    runs = E.run_named_fixtures()
    fire = runs["fixtures"]["fire"]
    silent = runs["fixtures"]["silent-search"]
    if not runs["both_states"]["pass"]:
        print("FAILED:CNL-0083 emit both-states did not pass; not writing SUCCESS artifact")
        print(json.dumps({k: compact(v) for k, v in runs["fixtures"].items()}, indent=2))
        return 1

    fire_rec = json.loads((HERE / "fixtures/fire/record.json").read_text(encoding="utf-8"))
    fire_vis = json.loads((HERE / "fixtures/fire/visits.json").read_text(encoding="utf-8"))["visits"]
    silent_rec = json.loads((HERE / "fixtures/silent-search/record.json").read_text(encoding="utf-8"))
    silent_vis = json.loads((HERE / "fixtures/silent-search/visits.json").read_text(encoding="utf-8"))["visits"]
    fire_tab = independent_recount(fire_rec["search_space"]["members"], fire_vis, RHS)
    silent_tab = independent_recount(silent_rec["search_space"]["members"], silent_vis, RHS)
    if fire_tab["proof"] is not True or silent_tab["proof"] is not False:
        print("FAILED:CNL-0083 emit independent recount disagrees with evaluator")
        return 1

    examples = G.parse_all_spec_examples()
    if any(not r["accepted"] for r in examples):
        print("FAILED:CNL-0083 emit A10 rejected a spec example")
        return 1

    anchor = catalog_anchor()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    art = {
        "unit_id": "CNL-0083",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0083",
        "kind": "executable-stopping-example",
        "title": "Executable stopping example: proof_of_impossibility == true",
        "question": QUESTION,
        "expression": G.UNIT_EXPRESSION,
        "spec_anchor": {
            "source": "_USER-PROMPTS.md:10942",
            "range": "_USER-PROMPTS.md:10937-10942",
            "quoted_verbatim": G.UNIT_EXPRESSION,
            "catalog": anchor,
            "six_required_examples": [
                {"line": line, "expression": expr} for line, expr in G.SPEC_EXAMPLES
            ],
        },
        "answer": {
            "on_disk_for_true": [
                "A ProofOfImpossibilityRecord JSON with all five mandatory fields: "
                "claim, search_space, methods, resource_limit, refuting_observation.",
                "search_space.kind == finite-closed-set with an explicit members list.",
                "A visit ledger (visits.json) whose member set equals search_space.members "
                "(coverage == cardinality), independently recountable.",
                "A bound predicate such that no member satisfies the existence side of the claim.",
                "resource_limit.space_exhausted_before_limit == true "
                "(the space ended; the search did not).",
                "refuting_observation names a concrete, in-principle-observable "
                "counterexample that would appear as a visit row in the same space.",
            ],
            "metric_binding": (
                "proof_of_impossibility is a boolean produced by validating those "
                "two files. The expression proof_of_impossibility == true reads the "
                "binding; it does not write the record."
            ),
            "evaluation_cadence": (
                "End-of-round snapshot of the files on disk. The expression is "
                "side-effect free. A withdrawn record makes the metric false before "
                "the next evaluation instant."
            ),
        },
        "negative_control": {
            "rejects": "unsuccessful search (incomplete coverage of a declared finite space)",
            "verbatim": NEGATIVE_CONTROL,
            "what_the_check_does_on_the_state_it_rejects": NEGATIVE_CONTROL,
            "planted_bad_reason": "unsuccessful-search-incomplete-coverage",
        },
        "a10_grammar": {
            "accepted_unchanged": True,
            "expression": G.UNIT_EXPRESSION,
            "examples": examples,
        },
        "fixture_runs": {
            "fire": compact(fire),
            "silent_search": compact(silent),
            "silent_unfalsifiable": compact(runs["fixtures"]["silent-unfalsifiable"]),
            "silent_circular": compact(runs["fixtures"]["silent-circular"]),
        },
        "independent_recount": {
            "method": "set-algebra over visit.member vs search_space.members, plus x*x tabulation",
            "rhs": RHS,
            "fire_coverage": fire_tab["coverage"],
            "fire_cardinality": fire_tab["cardinality"],
            "fire_squares": {str(k): v for k, v in fire_tab["squares"].items()},
            "fire_hits": fire_tab["hits"],
            "fire_proof": fire_tab["proof"],
            "silent_coverage": silent_tab["coverage"],
            "silent_cardinality": silent_tab["cardinality"],
            "silent_complete": silent_tab["complete"],
            "silent_proof": silent_tab["proof"],
            "disagreement_blocks": True,
        },
        "proof_record_schema": PROOF_RECORD_SCHEMA,
        "tests": [
            {
                "id": "both-states",
                "required": (
                    "the expression must FIRE on a fixture where it is true and stay "
                    "SILENT on a fixture where it is false"
                ),
                "result": "PASS" if runs["both_states"]["pass"] else "FAIL",
                "fire_verbatim": compact(fire)["verbatim"],
                "silent_verbatim": compact(silent)["verbatim"],
            },
            {
                "id": "a10-parse-unchanged",
                "required": "a parse test proving the expression is accepted by the A10 grammar unchanged",
                "result": "PASS",
                "expression": G.UNIT_EXPRESSION,
            },
            {
                "id": "negative-control-unsuccessful-search",
                "required": "negative control recorded verbatim: state what the check does on the state it is meant to reject",
                "result": "PASS",
                "verbatim": NEGATIVE_CONTROL,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0083-probe2-independent-recount",
            "method": "re-tabulate visit coverage and squares from fixtures, ignore author reason strings",
            "verdict": "PASS",
            "independent": True,
        },
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/CNL-0083/fixtures/fire/record.json",
                "role": "fire-fixture",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0083/fixtures/silent-search/record.json",
                "role": "negative-control-fixture",
            },
        ],
        "ts": now,
    }

    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(art, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL}")
    print(compact(fire)["verbatim"])
    print(compact(silent)["verbatim"])
    print("SUCCESS:CNL-0083 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
