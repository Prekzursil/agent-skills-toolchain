#!/usr/bin/env python3
"""Probe 1: every settled edge's test returns SIDE_A in world A and SIDE_B in world B."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import adjudicate as A  # noqa: E402

UNIT = "CNF-0068"


def main() -> int:
    unit = A.catalog_unit(UNIT)
    art_rel = str(unit["output_path"]).replace("\\", "/")
    schema_rel = str(unit["output_schema"]).replace("\\", "/")
    art_path = REPO / art_rel
    if not art_path.is_file() or art_path.stat().st_size < 200:
        print("FAILED:CNF-0068-probe1 artifact missing")
        return 1
    doc = json.loads(art_path.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        print("FAILED:CNF-0068-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") != "SUCCESS":
        print("FAILED:CNF-0068-probe1 state", doc.get("state"))
        return 1
    sentinel = str(unit.get("completion_sentinel") or "")
    blob = json.dumps(doc)
    if sentinel not in blob or "SUCCESS:CNF-0068" not in blob:
        print("FAILED:CNF-0068-probe1 sentinel absent")
        return 1
    if doc.get("never_adjudicated_by_agent_count") is not True:
        print("FAILED:CNF-0068-probe1 vote-count flag")
        return 1

    schema = json.loads((REPO / schema_rel).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = list(validator.iter_errors(doc))
    if errs:
        print("FAILED:CNF-0068-probe1 schema", errs[0].message)
        return 1
    for garbage in ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0068-probe1 schema vacuous")
            return 1

    by_id = {e["id"]: e for e in doc.get("edges") or []}
    settled = 0
    irreducible = 0
    for edge in A.load_fixture_edges():
        recorded = by_id.get(edge["id"])
        if not recorded:
            print("FAILED:CNF-0068-probe1 missing edge", edge["id"])
            return 1
        live, live_out = A.run_test(edge, A.live_world())
        if recorded["outcome"] != live:
            print(
                f"FAILED:CNF-0068-probe1 live drift {edge['id']} "
                f"art={recorded['outcome']} live={live}"
            )
            return 1
        if live == "IRREDUCIBLE":
            irreducible += 1
            ev = recorded.get("settling_evidence") or ""
            if len(ev) < 24:
                print("FAILED:CNF-0068-probe1 irreducible lacks settling_evidence", edge["id"])
                return 1
            continue
        proof = A.both_outcomes_proof(edge)
        if not proof or not proof.get("capable"):
            print("FAILED:CNF-0068-probe1 not capable of both outcomes", edge["id"], proof)
            return 1
        rec_proof = recorded.get("both_outcomes_proof") or {}
        if rec_proof.get("side_a_world_verdict") != "SIDE_A":
            print("FAILED:CNF-0068-probe1 proof A", edge["id"])
            return 1
        if rec_proof.get("side_b_world_verdict") != "SIDE_B":
            print("FAILED:CNF-0068-probe1 proof B", edge["id"])
            return 1
        always_a, _ = A.one_sided_always_a(edge, A.overlay_world(edge.get("world_b") or {}))
        if always_a != "SIDE_A":
            print("FAILED:CNF-0068-probe1 one-sided control broken")
            return 1
        if recorded.get("test_source") == "one_sided_always_a":
            print("FAILED:CNF-0068-probe1 one-sided test used as adjudicator")
            return 1
        settled += 1
        print(
            f"edge {edge['id']} live={live} both_outcomes=True "
            f"one_sided_rejected=True out={live_out}"
        )

    if settled < 1 or irreducible < 1:
        print(f"FAILED:CNF-0068-probe1 settled={settled} irreducible={irreducible}")
        return 1
    print(json.dumps({"pass": True, "probe": "probe1-both-outcomes", "settled": settled, "irreducible": irreducible, "unit_id": UNIT}))
    print("SUCCESS:CNF-0068-probe1 both-outcomes capability and live match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
