#!/usr/bin/env python3
"""Named probe 2: both-states — when the probe agrees with the panel, the
record still names the executable check as the reason, not the tally.

Also re-runs the both-states control (independent of probe 1's authoring
path) and checks same-spec determinism of the simulator slice.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenarios import spec_both_agree, spec_unanimous_wrong  # noqa: E402
from tools.council.simulate import (  # noqa: E402
    AGREEMENT,
    REASON_CHECK,
    REASON_TALLY,
    same_spec_byte_identical,
    run_council,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0274-probe2 {msg}")
    return 1


def main() -> int:
    agree_spec = spec_both_agree()
    rec = run_council(agree_spec, cwd=REPO)
    vote = rec["vote"]
    if not vote["unanimous"]:
        return fail("agreeing panel was not unanimous")
    if rec["outcome"] != agree_spec["gold"]:
        return fail(f"agreeing outcome={rec['outcome']!r}")
    if rec["outcome"] != vote["position"]:
        return fail("agreeing case: outcome should equal the panel position")
    if rec["reason"] != REASON_CHECK:
        return fail(f"agreeing reason={rec['reason']!r} not executable_check")
    if rec["reason"] == REASON_TALLY:
        return fail("agreeing case credited the tally")
    if rec["panel_classification"] != AGREEMENT:
        return fail(f"panel_classification={rec['panel_classification']!r}")
    if rec["dissent_kind"] is not None:
        return fail("agreeing case must not invent dissent")
    if rec["vote_used_as_outcome"] is not False:
        return fail("even agreement must not mark vote as the outcome reason")

    # Both-states: the disagreeing case (from the same harness) still exists
    # so a probe that only ever sees agreement cannot claim the gate works.
    disagree = run_council(spec_unanimous_wrong(), cwd=REPO)
    if disagree["outcome"] == disagree["vote"]["position"]:
        return fail("both-states: disagreeing case collapsed to the vote")
    if rec["outcome"] != disagree["outcome"]:
        return fail("both-states: agreeing and disagreeing outcomes diverged")
    if rec["reason"] != disagree["reason"]:
        return fail("both-states: reason must stay executable_check on both")

    det = same_spec_byte_identical(agree_spec, cwd=REPO)
    if not det["identical"]:
        return fail(f"same-spec transcripts diverged {det}")

    payload = {
        "probe": "probe2-both-states-reason-is-check",
        "unit_id": "TST-0274",
        "agree": {
            "proposition": rec["proposition"],
            "vote_position": vote["position"],
            "outcome": rec["outcome"],
            "reason": rec["reason"],
            "panel_classification": rec["panel_classification"],
            "check_command": rec["check"]["command"],
            "check_stdout_tail": (rec["check"]["stdout"] or "")[-500:],
        },
        "disagree": {
            "vote_position": disagree["vote"]["position"],
            "outcome": disagree["outcome"],
            "reason": disagree["reason"],
            "dissent_kind": disagree["dissent_kind"],
        },
        "determinism": det,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"agree_reason={rec['reason']} disagree_reason={disagree['reason']} "
        f"identical={det['identical']}"
    )
    print(
        "SUCCESS:TST-0274-probe2 both-states: agreement still credited to "
        "the executable check, not the tally"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
