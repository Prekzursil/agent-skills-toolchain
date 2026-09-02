#!/usr/bin/env python3
"""Probe 2: dissent-drop negative control + full-vs-compact decision identity.

Mechanically different from probe 1 (id-set reachability). This probe:
  1) recomputes a downstream decision from compacted form and compares it
     to the full-form decision (must match);
  2) drops one dissent DURING compaction and asserts reachability FIRES.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from tools.council.artifacts import compact as C  # noqa: E402
from scenario import DISSENTS, build_long_transcript  # noqa: E402


def main() -> int:
    transcript = build_long_transcript()
    good = C.compact(transcript)
    decision = C.decisions_match(transcript, good)
    good_reach = C.reachability(transcript, good)

    dropped_form, dropped_id = C.drop_one_dissent(transcript, DISSENTS[1]["id"])
    bad_reach = C.reachability(transcript, dropped_form)
    bad_decision = C.decisions_match(transcript, dropped_form)

    fired = bool(bad_reach["fires"]) and dropped_id in bad_reach["unreachable"]["dissent"]
    silent_on_good = (not good_reach["fires"]) and good_reach["zero_loss"]
    decision_ok = bool(decision["identical"])
    # Dropping a dissent must change the decision's dissent_ids (load-bearing).
    dissent_shift = decision["full"]["dissent_ids"] != bad_decision["compacted"]["dissent_ids"]

    print(
        json.dumps(
            {
                "probe": "probe2-negative-control-and-decision",
                "unit_id": "IMP-0348",
                "decision_identical": decision_ok,
                "full_winner": decision["full"]["winner_claim_id"],
                "compact_winner": decision["compacted"]["winner_claim_id"],
                "dropped_dissent_id": dropped_id,
                "fired_on_bad": fired,
                "silent_on_good": silent_on_good,
                "bad_unreachable_dissents": bad_reach["unreachable"]["dissent"],
                "bad_claim_id_loss": bad_reach["claim_id_loss"],
                "dissent_ids_shifted": dissent_shift,
            },
            sort_keys=True,
        )
    )
    print(
        f"decision_identical={decision_ok} winner={decision['full']['winner_claim_id']} "
        f"fired_on_bad={fired} silent_on_good={silent_on_good} dropped={dropped_id}"
    )

    if not silent_on_good:
        print("FAILED:IMP-0348-probe2 good compaction was not lossless")
        print(json.dumps(good_reach, sort_keys=True)[:2000])
        return 1
    if not decision_ok:
        print("FAILED:IMP-0348-probe2 full vs compacted decisions differ")
        print(json.dumps(decision, indent=2, sort_keys=True)[:4000])
        return 1
    if not fired:
        print("FAILED:IMP-0348-probe2 reachability did not FIRE after dissent drop")
        print(json.dumps(bad_reach["unreachable"], sort_keys=True))
        return 1
    if not dissent_shift:
        print("FAILED:IMP-0348-probe2 dropping a dissent left decision dissent_ids unchanged")
        return 1
    if dropped_id not in decision["full"]["dissent_ids"]:
        print("FAILED:IMP-0348-probe2 dropped id was not in the full decision")
        return 1

    print("SUCCESS:IMP-0348-probe2 negative control fires; decisions identical on good compact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
