#!/usr/bin/env python3
"""Drive every 3-valued row of each of the six stopping expressions.

Expected STOP/CONTINUE comes from explicit Kleene lookup tables, not from
StoppingRuntime, so a walker bug cannot grade its own homework.
"""
from __future__ import annotations

import itertools
from typing import Any, Optional

from expr import StoppingRuntime, kleene_and, kleene_or, state_from_assignment
from expressions import EXPRESSIONS, NEVER_TRUE
from mutant import mutant_and

Tri = Optional[bool]
TRI_VALUES: tuple[Tri, ...] = (False, None, True)

# Independent spec tables (not the if-chain in expr.kleene_and).
AND_TABLE = {
    (True, True): True,
    (True, False): False,
    (True, None): None,
    (False, True): False,
    (False, False): False,
    (False, None): False,
    (None, True): None,
    (None, False): False,
    (None, None): None,
}
OR_TABLE = {
    (True, True): True,
    (True, False): True,
    (True, None): True,
    (False, True): True,
    (False, False): False,
    (False, None): None,
    (None, True): True,
    (None, False): None,
    (None, None): None,
}


def tri_name(v: Tri) -> str:
    if v is True:
        return "T"
    if v is False:
        return "F"
    return "U"


def expected_value(connective: str, atom_vals: tuple[Tri, ...]) -> Tri:
    if connective == "ATOM":
        return atom_vals[0]
    if connective == "AND":
        acc: Tri = atom_vals[0]
        for nxt in atom_vals[1:]:
            acc = AND_TABLE[(acc, nxt)]
        return acc
    if connective == "OR":
        acc = atom_vals[0]
        for nxt in atom_vals[1:]:
            acc = OR_TABLE[(acc, nxt)]
        return acc
    raise ValueError(connective)


def expected_decision(value: Tri) -> str:
    return "STOP" if value is True else "CONTINUE"


def _jsonable_state(state: dict[str, Any], atoms) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for a in atoms:
        if a.name in state:
            out[a.name] = state[a.name]
        else:
            out[a.name] = "NOT-CHECKED"
    return out


def drive_expression(spec: dict, and_fn=kleene_and, or_fn=kleene_or) -> dict:
    rt = StoppingRuntime(spec["text"], and_fn=and_fn, or_fn=or_fn)
    atoms = rt.atoms
    n = len(atoms)
    expected_rows = 3**n
    rows = []
    mismatches = []
    for combo in itertools.product(TRI_VALUES, repeat=n):
        state = state_from_assignment(atoms, list(combo))
        observed_value = rt.evaluate(state)
        observed = rt.decide(state)
        spec_value = expected_value(spec["connective"], combo)
        spec_decision = expected_decision(spec_value)
        assignment = {atom.source: tri_name(want) for atom, want in zip(atoms, combo)}
        row = {
            "assignment": assignment,
            "state": _jsonable_state(state, atoms),
            "spec_value": tri_name(spec_value),
            "observed_value": tri_name(observed_value),
            "spec_decision": spec_decision,
            "observed_decision": observed,
            "match": observed == spec_decision
            and tri_name(observed_value) == tri_name(spec_value),
            "sampled": False,
        }
        rows.append(row)
        if not row["match"]:
            mismatches.append(row)
    if len(rows) != expected_rows:
        raise RuntimeError(
            f"{spec['id']}: got {len(rows)} rows, expected {expected_rows}"
        )
    stop_rows = [r for r in rows if r["observed_decision"] == "STOP"]
    return {
        "id": spec["id"],
        "spec_line": spec["spec_line"],
        "expression": spec["text"],
        "connective": spec["connective"],
        "atoms": [a.source for a in atoms],
        "domain": ["F", "U", "T"],
        "expected_row_count": expected_rows,
        "observed_row_count": len(rows),
        "sampled": False,
        "all_rows_observed": len(rows) == expected_rows,
        "mismatches": len(mismatches),
        "stop_row_count": len(stop_rows),
        "rows": rows,
        "conforms": len(mismatches) == 0 and len(rows) == expected_rows,
    }


def and_as_or_probe(and_fn=kleene_and) -> dict:
    """Partial evidence on every AND expression: U∧T and T∧U must CONTINUE."""
    findings = []
    fired = False
    for spec in EXPRESSIONS:
        if spec["connective"] != "AND":
            continue
        rt = StoppingRuntime(spec["text"], and_fn=and_fn)
        atoms = rt.atoms
        if len(atoms) != 2:
            raise RuntimeError(f"{spec['id']} AND expected 2 atoms, got {atoms}")
        for label, wants in (("U∧T", [None, True]), ("T∧U", [True, None])):
            state = state_from_assignment(atoms, wants)
            decision = rt.decide(state)
            value = rt.evaluate(state)
            behaves_as_or = decision == "STOP"
            if behaves_as_or:
                fired = True
            findings.append(
                {
                    "expression_id": spec["id"],
                    "expression": spec["text"],
                    "case": label,
                    "state": _jsonable_state(state, atoms),
                    "observed_value": tri_name(value),
                    "observed_decision": decision,
                    "spec_decision": "CONTINUE",
                    "and_behaved_as_or": behaves_as_or,
                }
            )
    return {
        "and_behaved_as_or": fired,
        "findings": findings,
        "honest_spec": "U∧T and T∧U are Unknown under Kleene AND and must CONTINUE",
    }


def proof_of_impossibility() -> dict:
    spec = next(s for s in EXPRESSIONS if s["id"] == "E6")
    rt = StoppingRuntime(spec["text"])
    atom = rt.atoms[0]
    exercised = []
    for want, label in ((True, "T"), (False, "F"), (None, "U")):
        state = state_from_assignment([atom], [want])
        exercised.append(
            {
                "atom": label,
                "state": _jsonable_state(state, [atom]),
                "decision": rt.decide(state),
                "value": tri_name(rt.evaluate(state)),
            }
        )
    stop_true = next(x for x in exercised if x["atom"] == "T")
    return {
        "expression": spec["text"],
        "reachable": stop_true["decision"] == "STOP",
        "exercised_explicitly": True,
        "rows": exercised,
        "note": "proof_of_impossibility == true is a first-class terminal, not skipped",
    }


def never_true_control() -> dict:
    rt = StoppingRuntime(NEVER_TRUE)
    samples = [
        {},
        {"unique_ideas": 0},
        {"unique_ideas": 99},
        {"unique_ideas": 100},
        {"unique_ideas": 101},
        {"unique_ideas": 1000},
    ]
    runs = []
    stopped = False
    for state in samples:
        d = rt.decide(state)
        v = rt.evaluate(state)
        if d == "STOP":
            stopped = True
        runs.append(
            {
                "state": dict(state) if state else {"unique_ideas": "NOT-CHECKED"},
                "value": tri_name(v),
                "decision": d,
            }
        )
    return {
        "expression": NEVER_TRUE,
        "never_stopped": not stopped,
        "verified_not_assumed": True,
        "runs": runs,
    }


def mutant_detector() -> dict:
    honest = and_as_or_probe(and_fn=kleene_and)
    broken = and_as_or_probe(and_fn=mutant_and)
    return {
        "fires_on_known_broken": broken["and_behaved_as_or"] is True,
        "silent_on_honest": honest["and_behaved_as_or"] is False,
        "honest": honest,
        "known_broken": broken,
        "fixture": (
            "mutant_and: U∧T and T∧U return True "
            "(OR-like under partial evidence)"
        ),
    }


def drive_all() -> dict:
    tables = [drive_expression(spec) for spec in EXPRESSIONS]
    poi = proof_of_impossibility()
    never = never_true_control()
    detector = mutant_detector()
    and_honest = detector["honest"]
    total_rows = sum(t["observed_row_count"] for t in tables)
    expected_total = sum(t["expected_row_count"] for t in tables)
    conforms = all(t["conforms"] for t in tables)
    return {
        "tables": tables,
        "total_rows_observed": total_rows,
        "total_rows_expected": expected_total,
        "sampled": False,
        "all_six_complete": len(tables) == 6 and total_rows == expected_total,
        "runtime_conforms": conforms,
        "and_as_or_on_honest": and_honest["and_behaved_as_or"],
        "proof_of_impossibility": poi,
        "never_true_control": never,
        "detector_control": detector,
    }
