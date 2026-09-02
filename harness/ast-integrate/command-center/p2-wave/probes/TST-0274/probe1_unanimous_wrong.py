#!/usr/bin/env python3
"""Named probe 1: unanimous-wrong panel loses to a passing check; probe ERROR
is NOT-CHECKED, never a silent fallback to the vote.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenarios import spec_probe_error, spec_unanimous_wrong  # noqa: E402
from tools.council.simulate import (  # noqa: E402
    MINORITY_VIEW,
    NOT_CHECKED,
    PANEL_ERROR,
    REASON_CHECK,
    REASON_PROBE_ERROR,
    REASON_TALLY,
    broken_vote_fallback_on_error,
    run_council,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0274-probe1 {msg}")
    return 1


def main() -> int:
    wrong = spec_unanimous_wrong()
    rec = run_council(wrong, cwd=REPO)
    vote = rec["vote"]
    if not vote["unanimous"]:
        return fail("panel was not unanimous")
    if vote["n_seats"] != 5:
        return fail(f"expected 5 seats, got {vote['n_seats']}")
    if vote["position"] == wrong["gold"]:
        return fail("planted wrong vote collided with gold digest")
    if rec["outcome"] != wrong["gold"]:
        return fail(f"probe did not win: outcome={rec['outcome']!r}")
    if rec["outcome"] == vote["position"]:
        return fail("outcome copied the unanimous wrong vote")
    if rec["reason"] != REASON_CHECK:
        return fail(f"reason={rec['reason']!r} not {REASON_CHECK}")
    if rec["vote_used_as_outcome"] is not False:
        return fail("vote_used_as_outcome must be false")
    if rec["dissent_kind"] == MINORITY_VIEW:
        return fail("unanimous-wrong recorded as minority view")
    if rec["dissent_kind"] != PANEL_ERROR:
        return fail(f"dissent_kind={rec['dissent_kind']!r} not panel_error")
    if rec["panel_classification"] != "error":
        return fail(f"panel_classification={rec['panel_classification']!r}")
    if rec["check"]["status"] != "PASS":
        return fail(f"check status={rec['check']['status']!r}")
    if rec["check"]["command"] != wrong["check_command"]:
        return fail("check command not recorded")
    if not rec["check"]["stdout"]:
        return fail("check stdout empty")

    err_spec = spec_probe_error()
    err = run_council(err_spec, cwd=REPO)
    if err["outcome"] != NOT_CHECKED:
        return fail(f"probe error outcome={err['outcome']!r} not NOT-CHECKED")
    if err["reason"] != REASON_PROBE_ERROR:
        return fail(f"probe error reason={err['reason']!r}")
    if err["outcome"] == err["vote"]["position"]:
        return fail("probe error silently fell back to the vote")
    if err["vote_used_as_outcome"] is not False:
        return fail("probe error used the vote as outcome")
    if err["check"]["status"] != "ERROR":
        return fail(f"error fixture status={err['check']['status']!r}")

    mutant = broken_vote_fallback_on_error(err_spec, cwd=REPO)
    if mutant["outcome"] != err["vote"]["position"]:
        return fail("mutant did not exhibit vote-fallback (detector blind)")
    if mutant["reason"] != REASON_TALLY:
        return fail("mutant reason was not unanimous_tally")
    if mutant["vote_used_as_outcome"] is not True:
        return fail("mutant did not mark vote_used_as_outcome")

    payload = {
        "probe": "probe1-unanimous-wrong-and-probe-error",
        "unit_id": "TST-0274",
        "unanimous_wrong": {
            "proposition": rec["proposition"],
            "vote_position": vote["position"],
            "unanimous": vote["unanimous"],
            "n_seats": vote["n_seats"],
            "check_command": rec["check"]["command"],
            "check_status": rec["check"]["status"],
            "check_asserted": rec["check"]["asserted"],
            "outcome": rec["outcome"],
            "reason": rec["reason"],
            "dissent_kind": rec["dissent_kind"],
        },
        "probe_error": {
            "outcome": err["outcome"],
            "reason": err["reason"],
            "vote_position": err["vote"]["position"],
            "vote_used_as_outcome": err["vote_used_as_outcome"],
        },
        "mutant_vote_fallback": {
            "outcome": mutant["outcome"],
            "reason": mutant["reason"],
            "vote_used_as_outcome": mutant["vote_used_as_outcome"],
        },
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"outcome={rec['outcome'][:12]}... vote={vote['position'][:12]}... "
        f"reason={rec['reason']} dissent={rec['dissent_kind']} "
        f"error_outcome={err['outcome']}"
    )
    print(
        "SUCCESS:TST-0274-probe1 unanimous-wrong probe wins; "
        "probe-error NOT-CHECKED; mutant fallback detectable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
