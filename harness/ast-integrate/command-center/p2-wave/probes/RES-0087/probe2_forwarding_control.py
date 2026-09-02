#!/usr/bin/env python3
"""Probe 2 (control): same example; per-child tallies restore flattened conclusion.

Negative control: dropping tallies back to labels re-breaks the conclusion.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from nested import (  # noqa: E402
    BLOCKED,
    COMPLETE,
    MINIMAL_FORWARDING_SET,
    flattened_member_majority,
    label_only_fanin,
    tally_forward_fanin,
)

ART = HERE.parents[3] / "command-center" / "research" / "RES-0087.json"


def main() -> int:
    labels = label_only_fanin()
    tallies = tally_forward_fanin()
    flat = flattened_member_majority()
    if labels["conclusion"] != BLOCKED:
        print("FAILED:RES-0087-probe2 label-only drifted")
        return 1
    if flat["conclusion"] != COMPLETE:
        print("FAILED:RES-0087-probe2 flattened drifted")
        return 1
    if tallies["conclusion"] != flat["conclusion"]:
        print("FAILED:RES-0087-probe2 tallies did not restore flattened conclusion")
        return 1
    if not tallies["disagreement_surfaced"]:
        print("FAILED:RES-0087-probe2 child disagreement not surfaced")
        return 1
    if not tallies["dissent_present"]:
        print("FAILED:RES-0087-probe2 within-child dissent not implied by tallies")
        return 1
    if tuple(tallies["forwarding_set"]) != MINIMAL_FORWARDING_SET:
        print("FAILED:RES-0087-probe2 forwarding set drifted")
        return 1
    # Negative control: labels-only still reversed on the same profile.
    if labels["conclusion"] == tallies["conclusion"]:
        print("FAILED:RES-0087-probe2 negative control collapsed")
        return 1
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "per_subcouncil_verdict_counts" not in text:
            print("FAILED:RES-0087-probe2 artifact omits minimal forwarding set")
            return 1
        if "SUCCESS:RES-0087 in the receipt AND a worked two-level example showing the loss plus the minimal forwarding set that fixes it" not in text:
            print("FAILED:RES-0087-probe2 sentinel absent from artifact")
            return 1
    out = {
        "probe": "probe2-forwarding-control",
        "unit_id": "RES-0087",
        "pass": True,
        "label_only": labels["conclusion"],
        "tally_forward": tallies["conclusion"],
        "flattened": flat["conclusion"],
        "restored": True,
        "disagreement_surfaced": True,
        "minimal_forwarding_set": list(MINIMAL_FORWARDING_SET),
        "negative_control_label_only_still_reversed": True,
        "per_subcouncil_verdict_counts": tallies["per_subcouncil_verdict_counts"],
    }
    print(json.dumps(out, sort_keys=True, default=str))
    print("SUCCESS:RES-0087-probe2 minimal forwarding set restores conclusion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
