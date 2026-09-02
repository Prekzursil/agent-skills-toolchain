#!/usr/bin/env python3
"""Probe 1: gatekeeper probe.

Vary only what the presenter forwards. A large verdict movement with the
seal off means the presenter, not the jury, decides. With the completeness
seal on, the same presenter variation must not move the verdict.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jury_model as J  # noqa: E402

OUT = HERE / "probe1-gatekeeper.raw.json"


def main() -> int:
    bad = J.planted_bad()
    good = J.known_good()
    mov_bad = bad["movement"]
    mov_good = good["movement"]
    doc = {
        "probe": "probe1-gatekeeper",
        "unit_id": "CNL-0034",
        "vary_only": "presenter forwarded subset",
        "held_fixed": ["underlying evidence pool", "juror scoring functions"],
        "planted_bad": {
            "gatekeeper": bad["gatekeeper"],
            "majority_a": mov_bad["majority_a"],
            "majority_b": mov_bad["majority_b"],
            "majority_flipped": mov_bad["majority_flipped"],
            "l1": mov_bad["l1"],
            "large_movement": mov_bad["large_movement"],
            "digest_equal": mov_bad["digest_equal"],
            "completeness_a": bad["completeness_a"],
            "completeness_b": bad["completeness_b"],
            "presenter_capture": bad["presenter_capture"],
        },
        "known_good": {
            "gatekeeper": good["gatekeeper"],
            "majority_a": mov_good["majority_a"],
            "majority_b": mov_good["majority_b"],
            "majority_flipped": mov_good["majority_flipped"],
            "l1": mov_good["l1"],
            "large_movement": mov_good["large_movement"],
            "digest_equal": mov_good["digest_equal"],
            "completeness_a": good["completeness_a"],
            "completeness_b": good["completeness_b"],
            "presenter_capture": good["presenter_capture"],
        },
        "signals": {
            "majority_tally": {
                "bad_flipped": mov_bad["majority_flipped"],
                "good_stable": not mov_good["majority_flipped"],
            },
            "packet_digest": {
                "bad_unequal": not mov_bad["digest_equal"],
                "good_equal": mov_good["digest_equal"],
            },
        },
        "pass": False,
    }
    ok = (
        mov_bad["majority_flipped"]
        and mov_bad["l1"] == 5
        and mov_bad["large_movement"]
        and bad["presenter_capture"]
        and not mov_bad["digest_equal"]
        and not bad["completeness_a"]
        and not bad["completeness_b"]
        and (not mov_good["majority_flipped"])
        and mov_good["l1"] == 0
        and (not mov_good["large_movement"])
        and (not good["presenter_capture"])
        and mov_good["digest_equal"]
        and good["completeness_a"]
        and good["completeness_b"]
        and good["check_silent"]
        and mov_bad["majority_a"] == J.CLAIMANT
        and mov_bad["majority_b"] == J.RESPONDENT
        and mov_good["majority_a"] == J.CLAIMANT
        and mov_good["majority_b"] == J.CLAIMANT
    )
    doc["pass"] = bool(ok)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "bad_flip="
        + str(mov_bad["majority_flipped"])
        + " bad_l1="
        + str(mov_bad["l1"])
        + " bad_digest_equal="
        + str(mov_bad["digest_equal"])
        + " capture="
        + str(bad["presenter_capture"])
        + " good_l1="
        + str(mov_good["l1"])
        + " good_digest_equal="
        + str(mov_good["digest_equal"])
        + " good_silent="
        + str(good["check_silent"])
    )
    if not ok:
        print("FAILED:CNL-0034-probe1 gatekeeper probe did not discriminate presenter capture")
        return 1
    print("SUCCESS:CNL-0034-probe1 gatekeeper: large movement without seal, zero with seal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
