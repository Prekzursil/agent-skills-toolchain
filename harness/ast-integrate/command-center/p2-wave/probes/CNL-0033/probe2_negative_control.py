#!/usr/bin/env python3
"""Probe 2: both-states negative control (catalog tests_required[1]).

The check is `clock_swap_changes_winner`:
  * FIRES on the planted-bad topology (timeout-wins / remaining-clock scoring)
  * SILENT on the known-good asymmetric-mandates topology

Both runs are printed verbatim. This script is also the catalog reviewer:
it re-runs the both-states control itself before any signing in the artifact.
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
    print(f"FAILED:CNL-0033-probe2 {msg}")
    return 1


def main() -> int:
    good = T.load_topology("good")
    bad = T.load_topology("timeout_wins")
    finding = T.load_world("finding")
    clean = T.load_world("clean")
    narrative = T.load_world("narrative")

    bad_find = T.detector_clock_swap_changes_winner(bad, finding)
    bad_clean = T.detector_clock_swap_changes_winner(bad, clean)
    good_find = T.detector_clock_swap_changes_winner(good, finding)
    good_clean = T.detector_clock_swap_changes_winner(good, clean)

    # Verbatim negative-control transcript (catalog: recorded verbatim).
    print("NEGATIVE_CONTROL_CHECK=clock_swap_changes_winner")
    print(
        "REJECT_STATE=timeout-wins-defective scores remaining clock; "
        "swapping the larger clock swaps the winner (budget, not truth)"
    )
    print(
        "verbatim_bad_finding "
        f"fired={bad_find['fired']} "
        f"winners={bad_find['winner_hi_red']}->{bad_find['winner_lo_red']} "
        f"verdict={bad_find['verdict']}"
    )
    print(
        "verbatim_bad_clean "
        f"fired={bad_clean['fired']} "
        f"winners={bad_clean['winner_hi_red']}->{bad_clean['winner_lo_red']} "
        f"verdict={bad_clean['verdict']}"
    )
    print(
        "verbatim_good_finding "
        f"fired={good_find['fired']} "
        f"winners={good_find['winner_hi_red']}->{good_find['winner_lo_red']} "
        f"verdict={good_find['verdict']}"
    )
    print(
        "verbatim_good_clean "
        f"fired={good_clean['fired']} "
        f"winners={good_clean['winner_hi_red']}->{good_clean['winner_lo_red']} "
        f"verdict={good_clean['verdict']}"
    )

    fired_on_bad = bool(bad_find["fired"] and bad_clean["fired"])
    silent_on_good = bool((not good_find["fired"]) and (not good_clean["fired"]))
    print(f"fired_on_bad={fired_on_bad} silent_on_good={silent_on_good}")
    if not fired_on_bad:
        return fail("check did not fire on planted-bad timeout-wins topology")
    if not silent_on_good:
        return fail("check fired on known-good asymmetric topology")

    # Narrative "finding" is not a confirmed artifact on the good topology.
    narr = T.simulate(good, narrative, red_clock=20, blue_clock=20)
    print(
        "narrative_good "
        f"outcome={narr['outcome']} winner={narr['winner']} "
        f"confirmed={narr['score_vector']['confirmed']} "
        f"rejected_events="
        f"{sum(1 for e in narr['events'] if e.get('kind')=='finding_rejected_evidence')}"
    )
    if narr["winner"] == "RED" or narr["score_vector"]["confirmed"] != 0:
        return fail("narrative_claim must not confirm a red win")
    if narr["outcome"] != "BLUE_WIN":
        return fail("narrative-only after exhausted attempts must be BLUE_WIN")

    trap = T.timeout_trap(good)
    print(
        "timeout_trap_not_blue_win "
        f"outcome={trap['outcome']} winner={trap['winner']}"
    )
    if trap["outcome"] == "BLUE_WIN":
        return fail("good topology awarded blue a timeout — scripted loss")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"artifact self-declared {doc.get('state')}")
        ncs = doc.get("negative_controls") or []
        if not ncs:
            return fail("artifact missing negative_controls")
        nc0 = ncs[0] if isinstance(ncs[0], dict) else {}
        if nc0.get("fired_on_bad_state") is not True:
            return fail("artifact did not record fire-on-bad")
        if nc0.get("silent_on_good_state") is not True:
            return fail("artifact did not record silent-on-good")
        reviewer = doc.get("reviewer") or {}
        if reviewer.get("both_states_rerun") is not True:
            return fail("reviewer did not mark both_states_rerun")

    print("SUCCESS:CNL-0033-probe2 both-states negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
