#!/usr/bin/env python3
"""Named probe 1: judge-swap stability on a frozen transcript.

Holds the even-moderator transcript fixed, applies five judge personas, and
reports the verdict distribution. A single swap is refused. Also records the
separate moderator-swap table (same personas, different moderator, new
transcript). Fail-closed if a judge mutates the frozen bytes or if the
ballot-invert control is silent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import council as C  # noqa: E402

OUT = HERE / "probe1-judge-swap.raw.json"


def main() -> int:
    frozen, sha = C.freeze_transcript("even")
    swap = C.judge_swap(frozen)
    if swap["transcript_sha256"] != sha:
        print("FAILED:TST-0268-probe1 frozen sha drifted")
        return 1
    if swap["n_judges"] < 5:
        print("FAILED:TST-0268-probe1 fewer than 5 judges (single swap is not a measurement)")
        return 1
    if set(swap["judge_ids"]) != set(C.JUDGE_IDS):
        print("FAILED:TST-0268-probe1 judge set mismatch")
        return 1
    inv = C.ballot_invert_control(frozen)
    if not inv["fired"]:
        print("FAILED:TST-0268-probe1 majority_ballot ignores ballots (invert silent)")
        return 1
    # Re-freeze and re-hash: two runs, identical transcript.
    frozen2, sha2 = C.freeze_transcript("even")
    if sha2 != sha:
        print("FAILED:TST-0268-probe1 same-seed transcript not byte-identical")
        return 1
    swap2 = C.judge_swap(frozen2)
    if swap2["distribution"] != swap["distribution"]:
        print("FAILED:TST-0268-probe1 judge-swap nondeterministic")
        return 1

    mod = C.moderator_swap_table()
    if not mod["transcripts_differ"]:
        print("FAILED:TST-0268-probe1 moderator swap did not change the transcript")
        return 1

    doc = {
        "probe": "probe1_judge_swap",
        "unit_id": C.UNIT,
        "transcript_sha256": sha,
        "n_judges": swap["n_judges"],
        "distribution": swap["distribution"],
        "agreement_rate": swap["agreement_rate"],
        "pairwise_agreement": swap["pairwise_agreement"],
        "unique_verdicts": swap["unique_verdicts"],
        "modal_verdict": swap["modal_verdict"],
        "theatre": swap["theatre"],
        "theatre_rule": swap["theatre_rule"],
        "rows": swap["rows"],
        "ballot_invert_control": inv,
        "moderator_swap": mod,
        "spec": C.SPEC_JUDGE_SINGLE_POINT,
        "pass": True,
    }
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    print(
        f"n_judges={swap['n_judges']} dist={swap['distribution']} "
        f"agreement={swap['agreement_rate']:.3f} unique={swap['unique_verdicts']} "
        f"theatre={swap['theatre']} invert_fired={inv['fired']} "
        f"mod_flipped={mod['n_judges_flipped']}"
    )
    print("SUCCESS:TST-0268-probe1 judge-swap distribution on frozen transcript")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
