#!/usr/bin/env python3
"""Probe 1: dominance and silence thresholds, plus even-council negative control.

Starts from the detector API and planted transcripts, not from the receipt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from council.antifail.participation import (  # noqa: E402
    DOMINANCE_MULTIPLE,
    SILENCE_MULTIPLE,
    analyze_council,
    flag_dominance,
    flag_silence,
)
from corpus import (  # noqa: E402
    above_dominance_volume,
    below_dominance_volume,
    even_council,
    silent_seat,
    substance_terse_monopoly,
    volume_filler_monopoly,
)


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0321-probe1 {msg}")
    return 1


def main() -> int:
    if not flag_dominance(0.51, 4):
        return _fail("0.51 of 4 seats must exceed 2/n=0.5")
    if flag_dominance(0.50, 4):
        return _fail("exactly 2/n must not fire (threshold is strictly greater)")
    if flag_dominance(0.49, 4):
        return _fail("0.49 of 4 must not dominate")
    if not flag_silence(0.0, 4, turns=0):
        return _fail("zero turns must be silent")
    if flag_silence(0.25, 4, turns=4):
        return _fail("fair share must not be silent")
    if not flag_silence(0.05, 4, turns=1):
        return _fail("0.05 < 0.25/4=0.0625 must be silent")
    if flag_silence(0.07, 4, turns=1):
        return _fail("0.07 > 0.0625 must not be silent")

    even = analyze_council(even_council())
    if even["flagged_volume"] or even["flagged_substance"]:
        return _fail(f"even council flagged {json.dumps({k: even[k] for k in ('volume_dominant','substance_dominant','volume_silent','substance_silent')})}")
    if not even["even"]:
        return _fail("even council even=false")
    shares_v = [round(s["volume_share"], 4) for s in even["seats"].values()]
    if max(shares_v) - min(shares_v) > 0.02:
        return _fail(f"even volume shares not tight {shares_v}")

    loud = analyze_council(volume_filler_monopoly())
    if "architect" not in loud["volume_dominant"]:
        return _fail(f"filler chair not volume-dominant {loud['volume_dominant']} shares={ {k: round(v['volume_share'],3) for k,v in loud['seats'].items()} }")
    if "architect" in loud["substance_dominant"]:
        return _fail("filler chair must not be substance-dominant")
    if not loud["measures_disagree"]:
        return _fail("volume-filler monopoly must disagree across measures")

    terse = analyze_council(substance_terse_monopoly())
    if "skeptic" not in terse["substance_dominant"]:
        return _fail(f"terse skeptic not substance-dominant {terse['substance_dominant']}")
    if "skeptic" in terse["volume_dominant"]:
        return _fail("terse skeptic must not be volume-dominant")
    if not terse["measures_disagree"]:
        return _fail("substance-terse monopoly must disagree")

    silent = analyze_council(silent_seat())
    if "critic" not in silent["volume_silent"] or "critic" not in silent["substance_silent"]:
        return _fail(f"critic not silent {silent['volume_silent']} {silent['substance_silent']}")
    if silent["seats"]["critic"]["turns"] != 0:
        return _fail("critic planted silent still has turns")

    below = analyze_council(below_dominance_volume())
    arch_v = below["seats"]["architect"]["volume_share"]
    if arch_v > below["dominance_threshold"]:
        return _fail(f"below fixture actually exceeds threshold {arch_v}")
    if "architect" in below["volume_dominant"]:
        return _fail("below-2x fixture fired volume dominance")

    above = analyze_council(above_dominance_volume())
    arch_v = above["seats"]["architect"]["volume_share"]
    if arch_v <= above["dominance_threshold"]:
        return _fail(f"above fixture under threshold {arch_v}")
    if "architect" not in above["volume_dominant"]:
        return _fail("above-2x fixture did not fire volume dominance")

    summary = {
        "pass": True,
        "probe": "probe1-thresholds",
        "dominance_multiple": DOMINANCE_MULTIPLE,
        "silence_multiple": SILENCE_MULTIPLE,
        "even_unflagged": True,
        "volume_filler_chair_volume_dominant": True,
        "substance_terse_skeptic_substance_dominant": True,
        "zero_turn_critic_silent": True,
        "below_2x_unflagged": True,
        "above_2x_flagged": True,
        "unit_id": "IMP-0321",
    }
    print(json.dumps(summary, sort_keys=True))
    print("even_unflagged=True volume_monopoly_disagrees=True substance_monopoly_disagrees=True silent_critic=True")
    print("SUCCESS:IMP-0321-probe1 dominance and silence thresholds; even council silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
