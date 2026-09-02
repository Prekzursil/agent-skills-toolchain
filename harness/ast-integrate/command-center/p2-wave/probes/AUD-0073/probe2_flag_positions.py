#!/usr/bin/env python3
"""Probe 2: position of each flag; inline vs trailing must diverge."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

UNIT = "AUD-0073"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, sort_keys=True, default=str)[:4000])
    return 1


def main() -> int:
    doc = E.scan()
    ctrl = E.control_diff(doc)
    flags = doc["flags"]
    bad_frac = [
        f["id"]
        for f in flags
        if not (0.0 <= float(f["position"]["position_frac"]) <= 1.0)
    ]
    payload = {
        "probe": "probe2-flag-positions",
        "unit_id": UNIT,
        "n_flags": doc["n_flags"],
        "n_in_final_15_percent": doc["n_in_final_15_percent"],
        "final_15_percent_rate": doc["final_15_percent_rate"],
        "position_verdict_counts": doc["position_verdict_counts"],
        "control": ctrl,
        "recorded_estate_baseline": doc["recorded_estate_baseline"],
        "bad_frac": bad_frac[:8],
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    if bad_frac:
        return fail("position_frac outside [0,1]", payload)
    if ctrl["inline_count"] < 1 or ctrl["trailing_count"] < 1:
        return fail("control fixtures missing from position probe", payload)
    if not ctrl["differ"]:
        return fail(
            "inline flag and trailing-section flag received the same position "
            "verdict; probe is not measuring position",
            payload,
        )
    if "INLINE" not in ctrl["inline_verdicts"]:
        return fail("inline control was not scored INLINE", payload)
    if "BURIED-TRAILING-SECTION" not in ctrl["trailing_verdicts"]:
        return fail("trailing control was not scored BURIED-TRAILING-SECTION", payload)
    # Presence-only mutant: same token in both docs would collapse verdicts.
    if set(ctrl["inline_verdicts"]) == set(ctrl["trailing_verdicts"]):
        return fail("control verdicts collapsed", payload)
    print(
        f"inline={ctrl['inline_verdicts']} trailing={ctrl['trailing_verdicts']} "
        f"final15={doc['n_in_final_15_percent']}/{doc['n_flags']}"
    )
    print(
        f"SUCCESS:{UNIT}-probe2 inline vs trailing position verdicts differ; "
        "each flag has a document-fraction"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
