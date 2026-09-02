#!/usr/bin/env python3
"""Own-fan-out must be in the actor set; MODELED rows need a B08/B10 test or MODELED-BUT-UNTESTED."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402

# Recorded before live_matrix() is called — independent of the receipt.
REVIEWER_PROPOSED_BEFORE_MATRIX = [
    "compromised or misaligned agent inside our own fan-out",
    "malicious package publisher",
]


def main() -> int:
    proposed = list(REVIEWER_PROPOSED_BEFORE_MATRIX)
    mapped = [C.map_reviewer_name(n) for n in proposed]

    matrix = C.live_matrix(C.REPO)
    ids = {a["id"] for a in matrix["actors"]}
    if C.OWN_FAN_OUT_ID not in ids:
        print("FAILED:BLD-0048-probe2 own fan-out actor missing from set")
        return 1
    if not matrix["own_fan_out_in_actor_set"]:
        print("FAILED:BLD-0048-probe2 own_fan_out_in_actor_set false")
        return 1
    if len(matrix["actors"]) < 10:
        print("FAILED:BLD-0048-probe2 actor set smaller than catalog list")
        return 1
    if not C.modeled_ok(matrix["actors"]):
        print("FAILED:BLD-0048-probe2 MODELED row lacks executable abuse test")
        return 1

    absent = []
    for name, aid in zip(proposed, mapped):
        if aid is None or aid not in ids:
            absent.append(name)
    if absent:
        print("FAILED:BLD-0048-probe2 reviewer actor absent: " + "; ".join(absent))
        return 1

    print(
        "own_fan_out_id="
        + C.OWN_FAN_OUT_ID
        + " in_set=True modeled="
        + str(matrix["own_fan_out_modeled"])
        + " MODELED="
        + str(matrix["counts"]["MODELED"])
        + " MODELED-BUT-UNTESTED="
        + str(matrix["counts"]["MODELED-BUT-UNTESTED"])
        + " UNMODELED="
        + str(matrix["counts"]["UNMODELED"])
        + " reviewer_mapped="
        + ",".join(str(m) for m in mapped)
    )
    print("SUCCESS:BLD-0048-probe2 own-fan-out set + modeled-implies-test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
