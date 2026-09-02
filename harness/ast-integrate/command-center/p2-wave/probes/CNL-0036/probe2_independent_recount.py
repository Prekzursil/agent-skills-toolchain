#!/usr/bin/env python3
"""Probe 2: independent 4-team recount + schema garbage control.

Does NOT call bracket.run_bracket or bracket.sweep. For four options the
standard bye-padded bracket collapses to semis (s1 vs s4) and (s2 vs s3)
then a final. Match winners are recovered by scanning the beats list
(a different field walk than set membership in bracket.py).

Disagreement with the artifact's n_distinct / counts blocks the unit.
Left-slot match tie-break on tied_wx is the forbidden rule: it splits
W/X 12/12, proving a slot-dependent tie-break reintroduces seeding.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from itertools import permutations
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0036-pairwise-tournament-topology-bracket-seeding-and-tie-break.md"
)
SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"
FIX = HERE / "fixtures.json"


def match(a: str, b: str, beats: list, ties: list, tie_break: str) -> str:
    for w, l in beats:
        if w == a and l == b:
            return a
        if w == b and l == a:
            return b
    for x, y in ties:
        if {x, y} == {a, b}:
            if tie_break == "lexicographic_id":
                return min(a, b)
            if tie_break == "left_slot":
                return a
            raise SystemExit(f"FAILED:CNL-0036-probe2 unknown tie_break {tie_break}")
    raise SystemExit(f"FAILED:CNL-0036-probe2 incomplete pair {a} vs {b}")


def four_team_winner(order: tuple[str, ...], beats: list, ties: list, tb: str) -> str:
    s1, s2, s3, s4 = order
    return match(
        match(s1, s4, beats, ties, tb),
        match(s2, s3, beats, ties, tb),
        beats,
        ties,
        tb,
    )


def recount(options: list[str], beats: list, ties: list, tb: str) -> dict:
    winners = [
        four_team_winner(order, beats, ties, tb) for order in permutations(options)
    ]
    counts = dict(sorted(Counter(winners).items()))
    n_perm = len(winners)
    n_distinct = len(counts)
    rate = max(counts.values()) / float(n_perm)
    return {
        "counts": counts,
        "invariance_rate": rate,
        "n_distinct_winners": n_distinct,
        "n_permutations": n_perm,
    }


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNL-0036-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0036" not in text:
        print("FAILED:CNL-0036-probe2 sentinel-absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNL-0036-probe2 self-declared", doc.get("state"))
        return 1

    fx = json.loads(FIX.read_text(encoding="utf-8"))
    options = list(fx["options"])
    tb = fx["tie_break_declared"]
    live = {}
    for name in ("cyclic4", "transitive4", "tied_wx"):
        prof = fx[name]
        live[name] = recount(options, prof["beats"], prof.get("ties") or [], tb)
        print(
            f"recount {name}: n_perm={live[name]['n_permutations']} "
            f"n_distinct={live[name]['n_distinct_winners']} "
            f"counts={live[name]['counts']} "
            f"invariance_rate={live[name]['invariance_rate']:.12f}"
        )

    if live["cyclic4"]["counts"] != {"W": 8, "X": 8, "Y": 8}:
        print("FAILED:CNL-0036-probe2 cyclic recount", live["cyclic4"]["counts"])
        return 1
    if live["transitive4"]["counts"] != {"W": 24}:
        print("FAILED:CNL-0036-probe2 transitive recount is not W x24")
        return 1
    if live["tied_wx"]["counts"] != {"W": 24}:
        print("FAILED:CNL-0036-probe2 lexicographic tied_wx is not W x24")
        return 1

    left = recount(
        options,
        fx["tied_wx"]["beats"],
        fx["tied_wx"]["ties"],
        "left_slot",
    )
    print(
        f"tie-break control: lexicographic counts={live['tied_wx']['counts']} "
        f"left_slot counts={left['counts']}"
    )
    if left["counts"] != {"W": 12, "X": 12}:
        print("FAILED:CNL-0036-probe2 left_slot did not split W/X 12/12")
        return 1

    rec = doc.get("sweep") or {}
    for name in ("cyclic4", "transitive4"):
        art_row = rec.get(name) or {}
        if art_row.get("counts") != live[name]["counts"]:
            print(
                f"FAILED:CNL-0036-probe2 disagreement {name}.counts "
                f"artifact={art_row.get('counts')} recount={live[name]['counts']}"
            )
            return 1
        if art_row.get("n_distinct_winners") != live[name]["n_distinct_winners"]:
            print(f"FAILED:CNL-0036-probe2 disagreement {name}.n_distinct")
            return 1
        if abs(float(art_row["invariance_rate"]) - live[name]["invariance_rate"]) > 1e-12:
            print(f"FAILED:CNL-0036-probe2 disagreement {name}.invariance_rate")
            return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(doc)
    rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNL-0036", "state": "SUCCESS"},
    ):
        try:
            jsonschema.Draft7Validator(schema).validate(garbage)
        except jsonschema.ValidationError:
            rejected += 1
            continue
        print(f"FAILED:CNL-0036-probe2 schema accepted garbage {garbage}")
        return 1
    if rejected != 3:
        print(f"FAILED:CNL-0036-probe2 garbage rejected {rejected}/3")
        return 1

    print("schema garbage rejected 3/3")
    print("SUCCESS:CNL-0036-probe2 independent recount schema-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
