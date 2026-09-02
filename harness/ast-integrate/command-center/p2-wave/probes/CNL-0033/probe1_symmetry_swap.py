#!/usr/bin/env python3
"""Probe 1: symmetry-swap control (catalog tests_required[0]).

Swapping which side gets the larger *clock* budget must not deterministically
swap the winner on the good topology. If it does, the topology measures budget
not truth.

Two mechanically independent signals:
  1) winner identity pair (hi-red vs lo-red)
  2) score_vector equality recomputed from the event log (confirmed /
     attempts_exhausted / coverage_complete) — a different field than winner
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import topology as T  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/CNL-0033-red-blue-adversarial-topology-with-asymmetric-mandates.md"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0033-probe1 {msg}")
    return 1


def main() -> int:
    good = T.load_topology("good")
    bad = T.load_topology("timeout_wins")
    finding = T.load_world("finding")
    clean = T.load_world("clean")

    # --- Signal 1: winner identity under clock swap ---
    good_find = T.clock_pair_runs(good, finding)
    good_clean = T.clock_pair_runs(good, clean)
    bad_find = T.clock_pair_runs(bad, finding)
    bad_clean = T.clock_pair_runs(bad, clean)

    print(
        "signal1_winner good_finding "
        f"{good_find['run_hi_red']['winner']}->{good_find['run_lo_red']['winner']} "
        f"swapped={good_find['winner_swapped']}"
    )
    print(
        "signal1_winner good_clean "
        f"{good_clean['run_hi_red']['winner']}->{good_clean['run_lo_red']['winner']} "
        f"swapped={good_clean['winner_swapped']}"
    )
    print(
        "signal1_winner defective_finding "
        f"{bad_find['run_hi_red']['winner']}->{bad_find['run_lo_red']['winner']} "
        f"swapped={bad_find['winner_swapped']}"
    )
    print(
        "signal1_winner defective_clean "
        f"{bad_clean['run_hi_red']['winner']}->{bad_clean['run_lo_red']['winner']} "
        f"swapped={bad_clean['winner_swapped']}"
    )

    if good_find["winner_swapped"] or good_clean["winner_swapped"]:
        return fail("good topology winner swapped after clock-only permutation")
    if good_find["run_hi_red"]["winner"] != "RED":
        return fail("planted finding must be a RED win on the good topology")
    if good_clean["run_hi_red"]["winner"] != "BLUE":
        return fail("clean surface must be a BLUE win on the good topology")
    if not bad_find["winner_swapped"] or not bad_clean["winner_swapped"]:
        return fail("defective timeout-wins must swap winner (detector vacuous)")

    # --- Signal 2: event-log recount of the score vector (different field) ---
    rec_hi = T.recount_from_events(good_find["events_hi_red"], finding)
    rec_lo = T.recount_from_events(good_find["events_lo_red"], finding)
    rec_clean_hi = T.recount_from_events(good_clean["events_hi_red"], clean)
    rec_clean_lo = T.recount_from_events(good_clean["events_lo_red"], clean)
    print(
        "signal2_recount finding "
        f"hi={rec_hi['recount_winner']} lo={rec_lo['recount_winner']} "
        f"confirmed={rec_hi['confirmed']}/{rec_lo['confirmed']} "
        f"vec_equal={rec_hi == rec_lo}"
    )
    print(
        "signal2_recount clean "
        f"hi={rec_clean_hi['recount_winner']} lo={rec_clean_lo['recount_winner']} "
        f"exhausted={rec_clean_hi['attempts_exhausted']}/"
        f"{rec_clean_lo['attempts_exhausted']} "
        f"vec_equal={rec_clean_hi == rec_clean_lo}"
    )
    if rec_hi != rec_lo or rec_clean_hi != rec_clean_lo:
        return fail("event-log score vector moved under clock-only permutation")
    if rec_hi["recount_winner"] != good_find["run_hi_red"]["winner"]:
        return fail("recount disagrees with engine winner on finding world")
    if rec_clean_hi["recount_winner"] != good_clean["run_hi_red"]["winner"]:
        return fail("recount disagrees with engine winner on clean world")
    if not good_find["score_vector_same"] or not good_clean["score_vector_same"]:
        return fail("engine score_vector drifted under clock swap")

    # Timeout trap: less clock for red must be INCONCLUSIVE, not a blue win.
    trap_good = T.timeout_trap(good)
    trap_bad = T.timeout_trap(bad)
    print(
        "timeout_trap "
        f"good={trap_good['outcome']}/{trap_good['winner']} "
        f"defective={trap_bad['outcome']}/{trap_bad['winner']} "
        f"attempts_used={trap_good['score_vector']['attempts_used']} "
        f"budget={finding['red_attempt_budget']}"
    )
    if trap_good["outcome"] != "INCONCLUSIVE" or trap_good["winner"] != "NONE":
        return fail("timeout with leftover attempts must be INCONCLUSIVE")
    if trap_good["score_vector"]["attempts_exhausted"]:
        return fail("timeout trap accidentally exhausted red attempts")
    if trap_bad["winner"] != "BLUE":
        return fail("defective timeout-wins must award blue the clock-starved red")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"artifact self-declared {doc.get('state')}")
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:CNL-0033" not in text:
            return fail("sentinel absent from artifact")
        swap = doc.get("symmetry_swap") or {}
        if swap.get("good_winner_swapped") is True:
            return fail("artifact claims good topology swapped")
        if swap.get("defective_winner_swapped") is not True:
            return fail("artifact does not record defective swap")

    print("SUCCESS:CNL-0033-probe1 symmetry-swap two-signal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
