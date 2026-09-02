#!/usr/bin/env python3
"""Strategic-voting detector: stated position vs submitted ballot + IRV pivot.

A participant is flagged iff ALL of:
  1. Latest stated ranking disagrees with latest submitted ballot.
  2. Replacing that ballot with the stated ranking changes the IRV winner.
  3. The stated ranking prefers the actual winner to the counterfactual
     (stated-ballot) winner — the misreport improved the outcome.

Honest revision is silent: when the latest stated ranking matches the latest
ballot, even if both changed from an earlier round, the detector does not fire.
Non-pivotal disagreements are also silent: disagreement without a winner
change is not evidence of tabulation influence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from irv import irv_winner, prefers, rankings_equal  # noqa: E402


def _last_of(history: list[dict], participant: str, kind: str) -> list[str] | None:
    last = None
    for event in history:
        if event.get("participant") == participant and event.get("kind") == kind:
            ranking = event.get("ranking")
            if isinstance(ranking, list) and ranking:
                last = [str(x) for x in ranking]
    return last


def detect(council: dict[str, Any]) -> dict[str, Any]:
    candidates = [str(c) for c in council.get("candidates") or []]
    history = list(council.get("history") or [])
    participants = list(council.get("participants") or [])
    if not participants:
        participants = sorted(
            {str(e.get("participant")) for e in history if e.get("participant")}
        )

    stated: dict[str, list[str] | None] = {}
    ballot: dict[str, list[str] | None] = {}
    for p in participants:
        stated[p] = _last_of(history, p, "stated_position")
        ballot[p] = _last_of(history, p, "ballot")

    voters = [p for p in participants if ballot[p]]
    actual_ballots = [ballot[p] for p in voters]  # type: ignore[misc]
    winner_actual = irv_winner(actual_ballots, candidates)

    findings: list[dict[str, Any]] = []
    inconsistencies_non_pivotal = 0
    honest_matches = 0
    for p in voters:
        s = stated[p]
        b = ballot[p]
        if s is None or b is None:
            continue
        if rankings_equal(s, b):
            honest_matches += 1
            continue
        cf_ballots = []
        for q in voters:
            cf_ballots.append(s if q == p else ballot[q])
        winner_if_stated = irv_winner(cf_ballots, candidates)
        if winner_actual == winner_if_stated:
            inconsistencies_non_pivotal += 1
            continue
        gained = (
            winner_actual is not None
            and winner_if_stated is not None
            and prefers(s, winner_actual, winner_if_stated)
        )
        if gained:
            findings.append(
                {
                    "participant": p,
                    "kind": "pivotal-misreport-gain",
                    "stated_ranking": s,
                    "submitted_ballot": b,
                    "winner_with_submitted_ballots": winner_actual,
                    "winner_if_stated_ballot": winner_if_stated,
                }
            )

    return {
        "fires": bool(findings),
        "findings": findings,
        "winner_actual": winner_actual,
        "honest_matches": honest_matches,
        "inconsistencies_non_pivotal": inconsistencies_non_pivotal,
        "voters": len(voters),
        "method": "irv",
        "council_id": council.get("id"),
    }


def load_council(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("FAILED:CNL-0093 detector usage: detector.py <fixture.json>")
        return 2
    path = Path(args[0])
    result = detect(load_council(path))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
