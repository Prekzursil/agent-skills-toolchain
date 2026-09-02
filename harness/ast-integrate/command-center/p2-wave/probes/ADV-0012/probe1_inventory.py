#!/usr/bin/env python3
"""Probe 1: extract dated assertions and name each original probe.

Does not re-measure. Confirming a stale pin here would mean the extractor
is being treated as a verifier — that is Probe 2's job.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import UNIT, probe1_payload  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    payload = probe1_payload()
    print(json.dumps(payload, sort_keys=True, default=str))
    cals = {c["id"] for c in payload["calibrations"]}
    if "CAL-MNN-STILL-LIVE" not in cals:
        return fail("missing known-stale calibration CAL-MNN-STILL-LIVE")
    if "CAL-RETIRED-TOOL-AVAILABLE" not in cals:
        return fail("missing known-stale calibration CAL-RETIRED-TOOL-AVAILABLE")
    if len(payload["planted_dated"]) < 3:
        return fail(f"planted dated rows={payload['planted_dated']}")
    g = payload["grounding_digest"]
    if not g["exists"]:
        return fail("ground-lane digest P2-GROUNDING.md missing")
    if not g["pins_zero_success"]:
        return fail("P2-GROUNDING.md no longer pins zero-success")
    if not g["pins_delivered_42"]:
        return fail("P2-GROUNDING.md no longer pins delivered-42")
    for row in payload["calibrations"]:
        if not row.get("original_probe"):
            return fail(f"{row['id']} missing original_probe")
    if not payload["pass"]:
        return fail("inventory conjunction failed")
    print(
        f"calibrations={len(payload['calibrations'])} "
        f"planted_dated={len(payload['planted_dated'])} "
        f"live_ledgers={payload['live_ledger_present_count']} "
        f"live_dated={payload['live_dated_count']}"
    )
    print("SUCCESS:ADV-0012-probe1 inventory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
