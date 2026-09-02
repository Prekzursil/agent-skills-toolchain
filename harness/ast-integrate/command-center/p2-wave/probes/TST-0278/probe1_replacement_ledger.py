#!/usr/bin/env python3
"""Probe 1: mid-run replacement — history intact, no inherited ballots.

Both-states: inherit_votes=False is the good path (replacement ballot count
for unattended rounds is 0). inherit_votes=True is the named defect; the
same detector MUST fire on that mutant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from council.participants.replace import (  # noqa: E402
    ballot_count,
    replace_occupant,
    vote_ledger,
)
from council.simulate import (  # noqa: E402
    default_personas,
    history_fingerprint,
    initial_state,
    run_round,
)


def _replacement() -> dict:
    p = default_personas()["persona-critic-replacement"]
    return {
        "persona_id": "persona-critic-replacement",
        "role": "critic",
        "script": p["script"],
    }


def run_swap(*, inherit_votes: bool) -> dict:
    st = initial_state()
    run_round(st)
    before = vote_ledger(st)
    history_r1 = history_fingerprint(st)
    departed_id = st["seats"]["seat-critic"]["active_occupant_id"]
    st["round"] = 2
    st = replace_occupant(
        st,
        "seat-critic",
        _replacement(),
        reason="recusal",
        inherit_votes=inherit_votes,
    )
    replacement_id = st["seats"]["seat-critic"]["active_occupant_id"]
    run_round(st)
    st["round"] = 3
    run_round(st)
    st["status"] = "complete"
    after = vote_ledger(st)
    unattended = [1]
    return {
        "state": st,
        "before": before,
        "after": after,
        "history_r1": history_r1,
        "history_after": history_fingerprint(st),
        "departed_id": departed_id,
        "replacement_id": replacement_id,
        "departed_r1": ballot_count(st, departed_id, unattended),
        "replacement_unattended": ballot_count(st, replacement_id, unattended),
        "replacement_attended": ballot_count(st, replacement_id, [2, 3]),
        "inherit_votes": inherit_votes,
    }


def _fail(msg: str, extra=None) -> int:
    print(f"FAILED:TST-0278-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, sort_keys=True, default=str)[:4000])
    return 1


def main() -> int:
    good = run_swap(inherit_votes=False)
    mutant = run_swap(inherit_votes=True)

    if good["state"]["status"] != "complete":
        return _fail("good path did not complete", good["state"].get("status"))
    if good["departed_r1"] != 1:
        return _fail(
            "departed occupant lost round-1 ballot (history not intact)",
            {"departed_r1": good["departed_r1"], "ledger_after": good["after"]},
        )
    if good["replacement_unattended"] != 0:
        return _fail(
            "replacement inherited ballots for unattended rounds",
            {
                "replacement_unattended": good["replacement_unattended"],
                "replacement_id": good["replacement_id"],
                "after": good["after"],
            },
        )
    if good["replacement_attended"] != 2:
        return _fail(
            "replacement did not vote in rounds it attended",
            {"replacement_attended": good["replacement_attended"]},
        )
    # History prefix: every round-1 position/vote still present with same occupant.
    after_r1 = [
        e
        for e in good["history_after"]
        if e.get("round") == 1 and e["kind"] in {"position", "vote"}
    ]
    if after_r1 != good["history_r1"]:
        return _fail(
            "round-1 history mutated by swap",
            {"before": good["history_r1"], "after": after_r1},
        )
    # Deliberation continued: round 2 and 3 events exist.
    later = [e for e in good["history_after"] if e.get("round") in {2, 3}]
    if len(later) < 6:
        return _fail("deliberation did not continue after swap", later)

    # Negative control: inherit mutant must be detected.
    if mutant["replacement_unattended"] <= 0:
        return _fail(
            "inherit-votes mutant was silent (detector vacuous)",
            {"replacement_unattended": mutant["replacement_unattended"]},
        )

    # Before/after ledgers differ by occupant id on the critic seat.
    if good["before"]["active_occupants"]["seat-critic"] == good["after"]["active_occupants"]["seat-critic"]:
        return _fail("active critic occupant unchanged after swap")

    out = {
        "pass": True,
        "probe": "probe1-replacement-ledger",
        "unit_id": "TST-0278",
        "vote_ledger_before": good["before"],
        "vote_ledger_after": good["after"],
        "departed_occupant_id": good["departed_id"],
        "replacement_occupant_id": good["replacement_id"],
        "replacement_ballot_count_unattended_rounds": good["replacement_unattended"],
        "unattended_rounds": [1],
        "departed_round1_ballots_retained": good["departed_r1"],
        "history_r1_intact": True,
        "deliberation_continued": True,
        "inherit_mutant_fired": True,
        "inherit_mutant_unattended_count": mutant["replacement_unattended"],
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print(
        "ledger_before_critic",
        good["before"]["active_occupants"]["seat-critic"],
        "ballots",
        len(good["before"]["ballots"]),
    )
    print(
        "ledger_after_critic",
        good["after"]["active_occupants"]["seat-critic"],
        "ballots",
        len(good["after"]["ballots"]),
        "replacement_unattended",
        good["replacement_unattended"],
    )
    print("SUCCESS:TST-0278-probe1 mid-run replacement, history intact, no inherited ballots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
