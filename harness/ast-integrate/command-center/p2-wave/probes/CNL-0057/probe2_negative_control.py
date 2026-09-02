#!/usr/bin/env python3
"""Probe 2: negative control. Records verbatim what the check rejects.

FIRES on vote-as-decision for a vote-harmful class.
SILENT on synthesis-only for the same seats/ballots.
SILENT on a genuine preference vote (same 2-1 shape, different class).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import synthesis_only as S  # noqa: E402
import reviewer as R  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0057-probe2 {msg}")
    return 1


def main() -> int:
    planted = S.load_fixture("diagnosis_split.json")
    good_syn = S.load_fixture("diagnosis_synthesis.json")
    pref = S.load_fixture("preference_ok.json")
    mixed = S.load_fixture("mixed_unsplit.json")

    print(f"negative_control_rejects: {S.REJECTS}")

    bad = S.detect(planted)
    good = S.detect(good_syn)
    ok_vote = S.detect(pref)
    mix = S.detect(mixed)

    print(f"planted_vote_on_diagnosis: {bad['output']}")
    print(f"synthesis_on_same_diagnosis: {good['output']}")
    print(f"vote_on_preference: {ok_vote['output']}")
    print(f"vote_on_mixed_unsplit: {mix['output']}")

    if not bad["fires"] or bad["output"] != S.FIRE:
        return fail("planted vote on diagnosis must FIRE manufactured_tally")
    if good["fires"] or good["output"] != S.SILENT:
        return fail("synthesis-only on diagnosis must be SILENT")
    if ok_vote["fires"] or ok_vote["output"] != S.SILENT:
        return fail("preference vote must be SILENT (not the rejected state)")
    if not mix["fires"]:
        return fail("unsplit mixed rollback vote must FIRE")

    if S.ballot_fingerprint(planted) != S.ballot_fingerprint(good_syn):
        return fail("planted and synthesis fixtures must share ballot bytes")

    print(
        "fired_on_bad=True silent_on_good=True "
        "silent_on_preference_vote=True "
        "both_states_recorded=True"
    )

    rc = R.main()
    if rc != 0:
        return fail("independent reviewer recount failed")

    print("SUCCESS:CNL-0057-probe2 negative control fires on manufactured tally")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
