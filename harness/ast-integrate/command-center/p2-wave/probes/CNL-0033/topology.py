#!/usr/bin/env python3
"""Red/blue topology with asymmetric mandates (CNL-0033).

Three currencies, not one:
  * clock            — a RIGHT to spend; never a scoring input on the good topology
  * red_attempts     — red's finding currency (existence search)
  * blue_coverage    — blue's obligation currency (named surface discharge)

Good scoring (findings-and-coverage):
  RED_WIN        confirmed_findings >= 1 (reproducible artifact only)
  BLUE_WIN       confirmed == 0 AND attempts exhausted AND coverage complete
  INCONCLUSIVE   every other terminal, including clock death with attempts left

Defective scoring (remaining-clock):
  the side with more leftover clock wins. Swapping the larger clock
  deterministically swaps the winner — the topology measures budget, not truth.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

ALLOWED_DEFAULT = (
    "repro_poc",
    "failing_control",
    "concrete_counterexample",
)


def load_json(name: str) -> dict[str, Any]:
    path = FIX / name
    return json.loads(path.read_text(encoding="utf-8"))


def load_topology(kind: str) -> dict[str, Any]:
    if kind == "good":
        return load_json("topology_good.json")
    if kind in {"timeout_wins", "defective", "bad"}:
        return load_json("topology_timeout_wins.json")
    raise KeyError(kind)


def load_world(kind: str) -> dict[str, Any]:
    names = {
        "finding": "world_finding.json",
        "clean": "world_clean.json",
        "narrative": "world_narrative.json",
    }
    return load_json(names[kind])


def _score_vector(
    confirmed: int,
    attempts_used: int,
    attempts_budget: int,
    coverage_done: int,
    coverage_req: int,
) -> dict[str, Any]:
    return {
        "confirmed": int(confirmed),
        "attempts_used": int(attempts_used),
        "attempts_exhausted": attempts_used >= attempts_budget,
        "coverage_done": int(coverage_done),
        "coverage_complete": coverage_done >= coverage_req,
    }


def _good_outcome(vec: dict[str, Any]) -> tuple[str, str]:
    if vec["confirmed"] >= 1:
        return "RED_WIN", "RED"
    if (
        vec["confirmed"] == 0
        and vec["attempts_exhausted"]
        and vec["coverage_complete"]
    ):
        return "BLUE_WIN", "BLUE"
    return "INCONCLUSIVE", "NONE"


def recount_from_events(
    events: list[dict[str, Any]],
    world: dict[str, Any],
) -> dict[str, Any]:
    """Second signal: recompute the score vector from the event log, not from
    the engine's outcome field. Different data field than `winner`.
    """
    confirmed = sum(1 for e in events if e.get("kind") == "finding_confirmed")
    attempts_used = sum(1 for e in events if e.get("kind") == "red_attempt")
    coverage_done = sum(1 for e in events if e.get("kind") == "blue_cover")
    vec = _score_vector(
        confirmed,
        attempts_used,
        int(world["red_attempt_budget"]),
        coverage_done,
        int(world["coverage_required"]),
    )
    outcome, winner = _good_outcome(vec)
    vec["recount_outcome"] = outcome
    vec["recount_winner"] = winner
    return vec


def simulate(
    topology: dict[str, Any],
    world: dict[str, Any],
    red_clock: int,
    blue_clock: int,
) -> dict[str, Any]:
    attempts_budget = int(world["red_attempt_budget"])
    coverage_req = int(world["coverage_required"])
    finding = world.get("finding")
    allowed = tuple(topology.get("allowed_evidence") or ALLOWED_DEFAULT)
    scoring = str(topology.get("scoring") or "findings-and-coverage")

    red_left = int(red_clock)
    blue_left = int(blue_clock)
    attempts_used = 0
    coverage_done = 0
    confirmed = 0
    events: list[dict[str, Any]] = []

    while True:
        red_acted = False
        blue_acted = False
        if attempts_used < attempts_budget and red_left > 0:
            attempts_used += 1
            red_left -= 1
            red_acted = True
            events.append({"kind": "red_attempt", "n": attempts_used})
            if (
                isinstance(finding, dict)
                and attempts_used >= int(finding["attempts_to_discover"])
            ):
                kind = str(finding.get("artifact_kind") or "")
                if kind in allowed:
                    confirmed += 1
                    events.append(
                        {
                            "kind": "finding_confirmed",
                            "artifact_kind": kind,
                            "attempt": attempts_used,
                        }
                    )
                else:
                    events.append(
                        {
                            "kind": "finding_rejected_evidence",
                            "artifact_kind": kind,
                            "attempt": attempts_used,
                        }
                    )
        if coverage_done < coverage_req and blue_left > 0:
            coverage_done += 1
            blue_left -= 1
            blue_acted = True
            events.append({"kind": "blue_cover", "n": coverage_done})

        if scoring != "remaining-clock" and confirmed >= 1:
            break
        if attempts_used >= attempts_budget and coverage_done >= coverage_req:
            break
        if not red_acted and not blue_acted:
            break

    vec = _score_vector(
        confirmed, attempts_used, attempts_budget, coverage_done, coverage_req
    )
    good_outcome, good_winner = _good_outcome(vec)

    if scoring == "remaining-clock":
        if red_left > blue_left:
            outcome, winner = "CLOCK_RED", "RED"
        elif blue_left > red_left:
            outcome, winner = "CLOCK_BLUE", "BLUE"
        else:
            outcome, winner = "CLOCK_TIE", "NONE"
    else:
        outcome, winner = good_outcome, good_winner

    return {
        "topology_id": topology.get("id"),
        "world_id": world.get("id"),
        "scoring": scoring,
        "clock_is_scoring_input": bool(topology.get("clock_is_scoring_input")),
        "initial_clocks": {"red": int(red_clock), "blue": int(blue_clock)},
        "remaining_clocks": {"red": red_left, "blue": blue_left},
        "score_vector": vec,
        "good_outcome_ignored_if_defective": good_outcome,
        "outcome": outcome,
        "winner": winner,
        "events": events,
    }


def clock_pair_runs(
    topology: dict[str, Any],
    world: dict[str, Any],
    clock_hi: int = 100,
    clock_lo: int = 10,
) -> dict[str, Any]:
    a = simulate(topology, world, red_clock=clock_hi, blue_clock=clock_lo)
    b = simulate(topology, world, red_clock=clock_lo, blue_clock=clock_hi)
    swapped = a["winner"] != b["winner"]
    vec_a = dict(a["score_vector"])
    vec_b = dict(b["score_vector"])
    # Signal 2 is score-vector equality (findings/coverage), not winner identity.
    vec_same = vec_a == vec_b
    return {
        "world_id": world.get("id"),
        "topology_id": topology.get("id"),
        "clocks_hi_lo": [clock_hi, clock_lo],
        "run_hi_red": {
            "winner": a["winner"],
            "outcome": a["outcome"],
            "score_vector": vec_a,
            "remaining_clocks": a["remaining_clocks"],
        },
        "run_lo_red": {
            "winner": b["winner"],
            "outcome": b["outcome"],
            "score_vector": vec_b,
            "remaining_clocks": b["remaining_clocks"],
        },
        "winner_swapped": swapped,
        "score_vector_same": vec_same,
        "events_hi_red": a["events"],
        "events_lo_red": b["events"],
    }


def timeout_trap(
    topology: dict[str, Any],
    world: dict[str, Any] | None = None,
    red_clock: int = 1,
    blue_clock: int = 100,
) -> dict[str, Any]:
    """Red still has unused attempts when clock dies. Good topology must NOT
    award BLUE_WIN (that would be a scripted loss for the side given less time).
    """
    w = world if world is not None else load_world("finding")
    run = simulate(topology, w, red_clock=red_clock, blue_clock=blue_clock)
    return run


def detector_clock_swap_changes_winner(
    topology: dict[str, Any],
    world: dict[str, Any],
    clock_hi: int = 100,
    clock_lo: int = 10,
) -> dict[str, Any]:
    """The check the negative control is meant to apply.

    FIRES when a clock-only permutation changes the winner.
    SILENT when the winner is invariant under that permutation.
    """
    pair = clock_pair_runs(topology, world, clock_hi, clock_lo)
    fired = bool(pair["winner_swapped"])
    return {
        "check": "clock_swap_changes_winner",
        "topology_id": topology.get("id"),
        "world_id": world.get("id"),
        "fired": fired,
        "winner_hi_red": pair["run_hi_red"]["winner"],
        "winner_lo_red": pair["run_lo_red"]["winner"],
        "score_vector_same": pair["score_vector_same"],
        "verdict": (
            "REJECT: winner swapped after clock-only permutation; "
            "topology measures budget not truth"
            if fired
            else "OK: winner invariant under clock-only permutation"
        ),
        "pair": pair,
    }
