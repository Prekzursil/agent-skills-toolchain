#!/usr/bin/env python3
"""Emit the CNL-0029 design note from live solver + bitmask recount."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import bitmask_recount as B  # noqa: E402
import ladder as L  # noqa: E402
import solver as S  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0029-incompatible-role-and-conflict-of-interest-checker-as-a-co.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
LOCAL_SCHEMA = (
    "command-center/p2-wave/probes/CNL-0029/council-design-note.schema.json"
)
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
SOLVER = "command-center/p2-wave/probes/CNL-0029/solver.py"
BITMASK = "command-center/p2-wave/probes/CNL-0029/bitmask_recount.py"
TEMPLATES = "command-center/p2-wave/probes/CNL-0029/fixtures/templates.json"
ROSTERS = "command-center/p2-wave/probes/CNL-0029/fixtures/rosters.json"
LADDER = "command-center/p2-wave/probes/CNL-0029/ladder.py"
QUESTION = (
    "Which role pairs are structurally incompatible on one seat "
    "(proposer judging its own proposal, critic voting on its own objection), "
    "and can the check be expressed as constraints a solver discharges rather "
    "than a hand-written if-ladder that silently misses a pair?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0029/probe1_exhaustive_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0029/probe2_independent_recount.py"
)


def ev(path: str, snippet: str, kind: str, claim: str, mechanism: str) -> dict:
    line = A.find_line(REPO / path, snippet)
    ok, why = A.resolve_anchor(REPO, path, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:CNL-0029 emit anchor {why}")
    return {
        "path": path,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "mechanism": mechanism,
        "anchor": f"{path}:{line}",
    }


def main() -> int:
    lib = S.load_library()
    matrix = S.enumerate_ordered_pairs(lib)
    bits = B.recount(lib)
    if (
        matrix["incompatible_ordered"] != bits["incompatible_ordered"]
        or matrix["incompatible_unordered"] != bits["incompatible_unordered"]
        or matrix["ordered_pair_count"] != bits["ordered_pair_count"]
    ):
        raise SystemExit("FAILED:CNL-0029 emit solver/bitmask disagreement")
    misses = L.missed_by_ladder(matrix["incompatible_unordered"], matrix["names"])
    if "judge+synthesiser" not in misses and "synthesiser+judge" not in misses:
        raise SystemExit(f"FAILED:CNL-0029 emit ladder did not miss synthesiser+judge: {misses}")
    rosters = S.load_rosters()
    controls = {k: S.check_roster(v, lib) for k, v in rosters.items()}
    bad = controls["planted_bad_self_review"]
    good = controls["known_good_pcj"]
    if not bad["fired"] or not good["silent"]:
        raise SystemExit("FAILED:CNL-0029 emit both-states failed")
    if not controls["custom_scribe_grader"]["fired"]:
        raise SystemExit("FAILED:CNL-0029 emit custom pair not caught")
    if controls["custom_scribe_grader"]["violations"][0]["constraint"] != S.STRUCTURAL:
        raise SystemExit("FAILED:CNL-0029 emit custom pair wrong constraint")
    if L.ladder_incompatible("scribe", "grader"):
        raise SystemExit("FAILED:CNL-0029 emit ladder unexpectedly knows scribe/grader")
    if not controls["planted_bad_coi"]["fired"] or not controls["known_good_coi_disclosed_author"]["silent"]:
        raise SystemExit("FAILED:CNL-0029 emit COI both-states failed")
    if not controls["planted_bad_undeclared_field"]["fired"]:
        raise SystemExit("FAILED:CNL-0029 emit undeclared-field silence")
    if not controls["custom_mystery_no_caps"]["fired"]:
        raise SystemExit("FAILED:CNL-0029 emit mystery role accepted")

    negative = {
        "fixture": "planted_bad_self_review",
        "intended_reject_state": "one seat holds proposer and judge",
        "fired": True,
        "silent": False,
        "violations": bad["violations"],
        "verbatim": json.dumps(bad, sort_keys=True),
    }
    unordered = matrix["incompatible_unordered"]
    answer = (
        "A same-seat pair is structurally incompatible iff the union of the two "
        "roles' capability predicates both authors and adjudicates (judge, vote, "
        "or veto) the same artifact kind. On the closed 8-role template set that "
        f"is exactly {matrix['incompatible_unordered_count']} unordered pairs "
        f"({', '.join(unordered)}); equivalently "
        f"{matrix['incompatible_ordered']} of {matrix['ordered_pair_count']} "
        "ordered dual-hat assignments, with "
        f"{matrix['compatible_ordered']} compatible. The check is those "
        "constraints plus declared-interest overlap on adjudicate capabilities "
        "and a hard fail when capability or interest fields are absent. A "
        "two-row named-pair if-ladder of the catalog examples (proposer+judge, "
        f"critic+juror) silently misses {len(misses)} template pairs including "
        "judge+synthesiser, and it accepts custom scribe+grader which the "
        "solver rejects. Independent bitmask recount matched the set-overlap "
        "solver on every cell. This is not a census of the 58 protocol records "
        "(file absent). SUCCESS:CNL-0029"
    )
    evidence = [
        {
            **ev(
                SOLVER,
                'STRUCTURAL = "SAME-SEAT-AUTHOR-ADJUDICATE"',
                "live-tree",
                "Structural COI is discharged as author/adjudicate kind overlap.",
                "python-set-overlap",
            ),
            "verdict": "CONFIRMED",
        },
        {
            **ev(
                BITMASK,
                "return (author_kinds(merged, n) & adjudicate_kinds(merged, n)) != 0",
                "live-tree",
                "Independent bitmask OR/AND recount of the same matrix.",
                "bitmask-OR-then-AND",
            ),
            "verdict": "CONFIRMED",
        },
        {
            **ev(
                TEMPLATES,
                "Closed 8-role library covering roles named by CNL-0022 through CNL-0032",
                "fixture",
                "Template set is closed and does not claim 58-protocol coverage.",
                "fixture-literal",
            ),
            "verdict": "CONFIRMED",
        },
        {
            **ev(
                CATALOG,
                "Which role pairs are structurally incompatible on one seat",
                "catalog",
                "Catalog question names the two examples and the if-ladder failure mode.",
                "catalog-field",
            ),
            "verdict": "CONFIRMED",
        },
        {
            **ev(
                ROSTERS,
                '"id": "planted-bad-self-review"',
                "fixture",
                "Planted-bad roster seats proposer and judge on one seat.",
                "fixture-literal",
            ),
            "verdict": "CONFIRMED",
        },
        {
            **ev(
                LADDER,
                "frozenset({\"proposer\", \"judge\"})",
                "live-tree",
                "If-ladder hard-codes only the two catalog examples.",
                "named-pair-ladder",
            ),
            "verdict": "REFUTED",
        },
    ]
    family = {
        "name": "cnl-0029-role-template-library",
        "expected_n": matrix["template_count"],
        "counted_n": matrix["template_count"],
        "members": [
            {
                "id": name,
                "record_id": name,
                "author": sorted((lib.get("templates") or {}).get(name, {}).get("author") or []),
                "judge": sorted((lib.get("templates") or {}).get(name, {}).get("judge") or []),
                "vote": sorted((lib.get("templates") or {}).get(name, {}).get("vote") or []),
                "veto": sorted((lib.get("templates") or {}).get(name, {}).get("veto") or []),
                "chair": sorted((lib.get("templates") or {}).get(name, {}).get("chair") or []),
            }
            for name in matrix["names"]
        ],
    }
    verdicts = [{"record_id": name, "verdict": "EXECUTABLE"} for name in matrix["names"]]
    claims = [
        {
            "id": "C1",
            "claim": "Same-seat incompatibility is author-and-adjudicate overlap on one artifact kind, not a name table.",
            "verdict": "CONFIRMED",
            "anchor": evidence[0]["anchor"],
        },
        {
            "id": "C2",
            "claim": (
                f"Exhaustive scan of the 8-template set yields "
                f"{matrix['incompatible_ordered']} incompatible and "
                f"{matrix['compatible_ordered']} compatible ordered pairs."
            ),
            "verdict": "CONFIRMED",
            "anchor": evidence[1]["anchor"],
        },
        {
            "id": "C3",
            "claim": "A two-row named-pair if-ladder of the catalog examples is a complete incompatible-role check.",
            "verdict": "REFUTED",
            "defect_locus": "DESIGN",
            "scoped_restatement": (
                f"The ladder hits proposer+judge and critic+juror and misses "
                f"{len(misses)} solver-incompatible unordered pairs: {misses}."
            ),
            "anchor": evidence[5]["anchor"],
            "why_locus": "ladder.py is the losing design, not a wording slip.",
        },
        {
            "id": "C4",
            "claim": "Custom scribe+grader (author proposal / judge proposal) is rejected by the solver and accepted by the ladder.",
            "verdict": "CONFIRMED",
            "anchor": evidence[4]["anchor"],
        },
        {
            "id": "C5",
            "claim": "This unit enumerated every role named across the 58 catalogued protocol records.",
            "verdict": "REFUTED",
            "defect_locus": "SENTENCE",
            "scoped_restatement": (
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent. The template "
                "set is the closed 8-role library named by CNL-0022..CNL-0032."
            ),
            "anchor": evidence[2]["anchor"],
            "why_locus": "Coverage of 58 protocols is a catalog-adjacent sentence, not a rule in the solver.",
        },
        {
            "id": "C6",
            "claim": "The check fires on planted-bad proposer+judge and is silent on a three-seat PCJ roster.",
            "verdict": "CONFIRMED",
            "anchor": evidence[4]["anchor"],
        },
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNL-0029",
        "id": "CNL-0029",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:CNL-0029",
        "completion_sentinel": "SUCCESS:CNL-0029",
        "title": "Incompatible-role and conflict-of-interest checker as a constraint solver",
        "question": QUESTION,
        "answer": answer,
        "family": family,
        "verdicts": verdicts,
        "ts": now,
        "output_schema": SCHEMA,
        "claims": claims,
        "evidence": evidence,
        "matrix": {
            "template_names": matrix["names"],
            "template_count": matrix["template_count"],
            "ordered_pair_count": matrix["ordered_pair_count"],
            "incompatible_ordered": matrix["incompatible_ordered"],
            "compatible_ordered": matrix["compatible_ordered"],
            "incompatible_unordered": unordered,
            "incompatible_unordered_count": matrix["incompatible_unordered_count"],
            "ladder_named_pairs": L.ladder_scan(matrix["names"])["named_pairs"],
            "ladder_misses": misses,
            "cells": [
                {
                    "a": r["a"],
                    "b": r["b"],
                    "incompatible": r["incompatible"],
                    "kinds": r["kinds"],
                }
                for r in matrix["rows"]
            ],
            "bitmask_agree": True,
            "computed_not_asserted": True,
        },
        "both_states": {
            "planted_bad": {
                "id": "planted_bad_self_review",
                "fired": True,
                "silent": False,
                "verbatim": negative["verbatim"],
            },
            "known_good": {
                "id": "known_good_pcj",
                "fired": False,
                "silent": True,
                "verbatim": json.dumps(good, sort_keys=True),
            },
            "coi_planted_bad_fired": True,
            "coi_known_good_silent": True,
        },
        "negative_control": negative,
        "custom_role_contract": {
            "must_supply": [
                "author/judge/vote/veto/chair predicates over artifact kinds",
                "declared_interests list (may be empty)",
            ],
            "scribe_grader_solver_fired": True,
            "scribe_grader_ladder_fired": False,
            "mystery_no_caps_refused": True,
        },
        "tests": [
            {
                "id": "exhaustive-matrix",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "independent-bitmask-recount",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0029-probe2-bitmask-recount",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": "Re-tabulate every ordered pair from fixtures/templates.json via bitmask_recount.py without reading this note's matrix field as the source of truth.",
        },
        "residual_unknowns": [
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json and 11-COUNCIL-SPECIFICATION.schema.json are not on this worktree, so this note does not claim a 58-protocol role census (that is CNL-0028).",
            "CNL-0022 role-mandate schema is not delivered here; capability predicates are the contract a custom role must supply for this checker to reason.",
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {"path": LOCAL_SCHEMA, "exists": True, "role": "supporting"},
            {"path": SOLVER, "exists": True, "role": "supporting"},
            {"path": BITMASK, "exists": True, "role": "supporting"},
            {"path": TEMPLATES, "exists": True, "role": "supporting"},
            {"path": ROSTERS, "exists": True, "role": "supporting"},
        ],
        "signals": [
            {
                "id": "S1",
                "mechanism": "python-set-overlap",
                "incompatible_ordered": matrix["incompatible_ordered"],
                "compatible_ordered": matrix["compatible_ordered"],
            },
            {
                "id": "S2",
                "mechanism": "bitmask-OR-then-AND",
                "incompatible_ordered": bits["incompatible_ordered"],
                "compatible_ordered": bits["compatible_ordered"],
            },
        ],
    }
    # Catalog schema is a generated $ref shim to ast-integrate.invalid.
    # Validate the live note against the per-unit schema instead.
    schema = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0029 emit schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({}, {"blob": "x" * 200}, {"unit_id": "NOPE", "state": "SUCCESS"}):
        if not list(validator.iter_errors(g)):
            print("FAILED:CNL-0029 emit schema accepted garbage")
            return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print(
        f"incompatible_ordered={matrix['incompatible_ordered']} "
        f"compatible_ordered={matrix['compatible_ordered']} "
        f"unordered={matrix['incompatible_unordered_count']}"
    )
    print("SUCCESS:CNL-0029 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
