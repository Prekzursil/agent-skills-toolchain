#!/usr/bin/env python3
"""Named probe 1: cross-team token scan over delivered prompts, required zero.

Also checks team assignment and scoring on the same live exchange.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.topology.redblue import (  # noqa: E402
    RecordingKernel,
    default_fixture_assignment,
    default_fixture_moves,
    mint_token,
    run_clean_fixture,
    scan_cross_team_tokens,
    score_exchange,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0284-probe1 {msg}")
    return 1


def main() -> int:
    assignment = default_fixture_assignment()
    if set(assignment.values()) != {"red", "blue"}:
        return fail(f"assignment not a partition: {assignment}")
    if assignment["red-1"] != "red" or assignment["blue-1"] != "blue":
        return fail(f"default assignment drifted: {assignment}")

    moves = default_fixture_moves()
    expected = score_exchange(moves)
    if expected.scores != {"red": 3, "blue": 2} or expected.winner != "red":
        return fail(f"scorecard drifted: {expected.as_dict()}")

    kernel = RecordingKernel()
    result = run_clean_fixture(kernel=kernel)
    if result.findings:
        return fail(f"clean scan fired: {result.as_dict()['findings']}")
    live = scan_cross_team_tokens(result.prompts)
    if live:
        return fail(f"rescanned findings { [f.as_dict() for f in live] }")
    if result.turns_executed != len(result.seats):
        return fail(
            f"turns_executed={result.turns_executed} seats={len(result.seats)}"
        )
    if kernel.turns_executed != len(kernel.events):
        return fail("kernel turn count diverged from event log")
    if result.scorecard.as_dict() != expected.as_dict():
        return fail("live scorecard != unit scorecard")

    blue_token = mint_token("blue", "clean-fixture:blue")
    red_token = mint_token("red", "clean-fixture:red")
    for prompt in result.prompts:
        if prompt.team == "red" and blue_token in prompt.text:
            return fail(f"blue canary in red prompt {prompt.seat_id}")
        if prompt.team == "blue" and red_token in prompt.text:
            return fail(f"red canary in blue prompt {prompt.seat_id}")
        own = red_token if prompt.team == "red" else blue_token
        if own not in prompt.text:
            return fail(f"own huddle canary missing from {prompt.seat_id}")

    payload = {
        "probe": "probe1-delivered-prompt-scan",
        "unit_id": "IMP-0284",
        "prompt_count": len(result.prompts),
        "finding_count": 0,
        "findings": [],
        "assignment": assignment,
        "scorecard": result.scorecard.as_dict(),
        "turns_executed": result.turns_executed,
        "turns_recorded": len(kernel.events),
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "finding_count=0 score red=3 blue=2 winner=red "
        f"turns={result.turns_executed}"
    )
    print("SUCCESS:IMP-0284-probe1 cross-team scan over delivered prompts is zero")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
