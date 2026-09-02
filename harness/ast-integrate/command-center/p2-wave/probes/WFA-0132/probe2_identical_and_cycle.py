#!/usr/bin/env python3
"""Probe 2: identical arms stay UNDECIDED; planted Condorcet cycle is reported.

Independent of probe 1. Recomputes the pairwise graph from sequential winners
and requires cycles to be first-class. A naive always-left reducer must mint
a false winner on the identical pair (negative control).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_repo(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "tools" / "foundry" / "tournament.py").is_file():
            return p
    raise SystemExit("FAILED:WFA-0132-probe2 repo root not found")


REPO = find_repo(HERE)
sys.path.insert(0, str(REPO))

from tools.foundry.tournament import (  # noqa: E402
    condorcet_cycles,
    naive_hides_identical_winner,
    planted_cycle_ok,
    planted_identical_ok,
    run_tournament,
)

ART = REPO / (
    "command-center/foundry/"
    "WFA-0132-pairwise-workflow-tournament-runner-with-a-statistic.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0132-probe2 {msg}")
    return 1


def main() -> int:
    tour = run_tournament()
    identical = planted_identical_ok(tour)
    cycle = planted_cycle_ok(tour)
    naive = naive_hides_identical_winner()
    recomputed = condorcet_cycles(tour["pairs"])
    if not identical["ok"]:
        return fail(f"identical arms produced a winner {identical}")
    if not cycle["ok"]:
        return fail(f"planted cycle not reported {cycle}")
    if recomputed != tour["condorcet_cycles"]:
        return fail(
            f"cycle recompute drifted {recomputed} vs {tour['condorcet_cycles']}"
        )
    if not naive["ok_control_fires"]:
        return fail(
            f"naive always-left control did not mint a false winner {naive}"
        )
    if tour["ranking_allowed"] is not False:
        return fail("ranking_allowed must be false while a cycle exists")
    if not tour["undecided_pairs"]:
        return fail("undecided_pairs must be first-class and non-empty")

    clone_row = next(
        r
        for r in tour["pairs"]
        if r["arm_a"] == "src-alpha" and r["arm_b"] == "fus-clone-alpha"
    )
    if clone_row["ties"] != clone_row["n_max"]:
        return fail(f"identical pair should be all ties {clone_row}")

    if ART.is_file() and ART.stat().st_size > 200:
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:WFA-0132" not in text:
            return fail("sentinel absent from artifact")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"self-declared {doc.get('state')}")
        if not (doc.get("undecided_pairs") or []):
            return fail("artifact omitted undecided_pairs")
        if not (doc.get("condorcet_cycles") or []):
            return fail("artifact omitted condorcet_cycles")
        rec_id = (doc.get("plants") or {}).get("identical_undecided") or {}
        if rec_id.get("ok") is not True:
            return fail("artifact did not record identical-UNDECIDED PASS")
        rec_cy = (doc.get("plants") or {}).get("condorcet_cycle_reported") or {}
        if rec_cy.get("ok") is not True:
            return fail("artifact did not record cycle PASS")

    payload = {
        "probe": "probe2-identical-and-cycle",
        "unit_id": "WFA-0132",
        "identical_undecided": True,
        "cycle": tour["condorcet_cycles"],
        "undecided_n": len(tour["undecided_pairs"]),
        "naive_false_winner": True,
        "ranking_allowed": tour["ranking_allowed"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:WFA-0132-probe2 identical arms UNDECIDED; planted cycle reported"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
