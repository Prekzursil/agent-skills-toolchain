#!/usr/bin/env python3
"""Probe 2: both-states negative control.

GREEN: live scan has a named NOT_TRANSFERABLE mechanism with a blocking reason.
RED: the same detector rejects a mutant in which every mechanism TRANSFER.
Silent-in-both-states is a detector failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402


def main() -> int:
    if not C.ART.is_file():
        print("FAILED:RES-0137-probe2 artifact missing")
        return 1
    live = C.load_json(C.ART)
    good = C.transfer_scan(live)
    mutant = C.everything_transfers_mutant(live)
    bad = C.transfer_scan(mutant)
    payload = {
        "probe": "probe2-negative-control",
        "unit_id": "RES-0137",
        "live_pass": good["pass"],
        "live_errors": good["errors"],
        "mutant_pass": bad["pass"],
        "mutant_errors": bad["errors"],
        "mutant_fired": (not bad["pass"])
        and any(
            e
            in {
                "negative-control-absent",
                "control-plane-unmodelled",
                "everything-transfers",
                "negative-control-not-marked",
                "blocking-reason-thin",
            }
            or e.startswith("negative-control")
            for e in bad["errors"]
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    if not good["pass"]:
        print("FAILED:RES-0137-probe2 live scan rejected")
        return 1
    if bad["pass"]:
        print("FAILED:RES-0137-probe2 mutant accepted (silent in both states)")
        return 1
    if not payload["mutant_fired"]:
        print("FAILED:RES-0137-probe2 mutant red for the wrong reason")
        return 1
    print(
        f"fired_on_bad={payload['mutant_fired']} silent_on_good={good['pass']} "
        f"mutant_errors={bad['errors'][:4]}"
    )
    print("SUCCESS:RES-0137-probe2 both-states negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
