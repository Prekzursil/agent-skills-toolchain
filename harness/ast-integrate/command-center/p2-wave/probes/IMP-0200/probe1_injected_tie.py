#!/usr/bin/env python3
"""Probe 1: injected exact-tie is a TIE; both-states with a clear winner.

A detector that always reports TIE would pass the injected pair and fail the
champion-vs-weak pair. A detector that always orders (name sort) would pass
the winner pair and fail the injected tie. Both states must hold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "command-center"))

from workflow_tournament import (  # noqa: E402
    clear_winner_ids,
    compare_pair,
    eval_cases,
    injected_tie_ids,
    matched_corpus,
    scorers,
)

ART = REPO / "command-center/receipts/IMP-0200.json"


def main() -> int:
    s = scorers()
    cases = eval_cases(matched_corpus())
    if len(cases) < 8:
        print(f"FAILED:IMP-0200-probe1 eval n={len(cases)} < 8")
        return 1

    t_a, t_b = injected_tie_ids()
    w_a, w_b = clear_winner_ids()

    tie = compare_pair(t_a, t_b, s[t_a], s[t_b], cases)
    win = compare_pair(w_a, w_b, s[w_a], s[w_b], cases)

    print(json.dumps({
        "tie_pair": [t_a, t_b],
        "tie_outcome": tie.outcome,
        "tie_wins": [tie.wins_a, tie.wins_b],
        "winner_pair": [w_a, w_b],
        "winner_outcome": win.outcome,
        "winner_wins": [win.wins_a, win.wins_b],
        "n_cases": len(cases),
    }, sort_keys=True))

    if tie.outcome != "TIE":
        print(f"FAILED:IMP-0200-probe1 injected pair ordered as {tie.outcome}")
        return 1
    if tie.wins_a != 0 or tie.wins_b != 0:
        print("FAILED:IMP-0200-probe1 injected pair was not an exact-zero vector")
        return 1
    if win.outcome != "A_WINS":
        print(f"FAILED:IMP-0200-probe1 clear winner not ordered ({win.outcome})")
        return 1
    if win.wins_a <= win.wins_b:
        print("FAILED:IMP-0200-probe1 winner state has no paired margin")
        return 1

    # Name-sort control: if we ordered by id, twin-left < twin-right would
    # manufacture a winner. The live comparator must not.
    if t_a < t_b and tie.outcome == "A_WINS":
        print("FAILED:IMP-0200-probe1 looks like a name-ordered fabricated verdict")
        return 1

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:IMP-0200-probe1 self-declared {st}")
            return 1
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:IMP-0200" not in text:
            print("FAILED:IMP-0200-probe1 sentinel absent")
            return 1

    print("SUCCESS:IMP-0200-probe1 injected-tie both-states with clear winner")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
