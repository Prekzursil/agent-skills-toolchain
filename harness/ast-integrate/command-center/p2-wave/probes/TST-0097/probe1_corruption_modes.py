#!/usr/bin/env python3
"""Named probe 1: each catalog corruption mode is detected and rebuilt, never served.

Catalog tests_required: test_each_corruption_mode_is_detected
Evidence: one corruption mode per case with the detection mechanism named;
serving a corrupt entry silently is a P0.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from cache import (  # noqa: E402
    DETECT_LEFTOVER_TMP,
    DETECT_TRUNCATED,
    DETECT_UNREADABLE,
    DETECT_WRONG_HASH,
    LEFTOVER_TMP,
    TRUNCATED,
    UNREADABLE,
    WRONG_HASH,
)
from scenario import run_all_modes, run_intact_negative_control, verdict_modes  # noqa: E402

EXPECT_DETECT = {
    TRUNCATED: DETECT_TRUNCATED,
    WRONG_HASH: DETECT_WRONG_HASH,
    UNREADABLE: DETECT_UNREADABLE,
    LEFTOVER_TMP: DETECT_LEFTOVER_TMP,
}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0097-p1-") as tmp:
        root = Path(tmp)
        rows = run_all_modes(root)
        intact = run_intact_negative_control(root)

    ok, why = verdict_modes(rows)
    named = all(
        r.get("detection_mechanism") == EXPECT_DETECT[r["corruption_mode"]]
        for r in rows
    )
    leftover = next(r for r in rows if r["corruption_mode"] == LEFTOVER_TMP)
    leftover_ok = (
        leftover.get("leftover_cleared")
        and leftover.get("payload_sha256_match")
        and leftover.get("quarantined")
        and leftover.get("rebuilt")
        and not leftover.get("published_after_interrupt")
    )

    if intact.get("rebuilt") or intact.get("quarantined") or not intact.get("hit"):
        print("FAILED:TST-0097-probe1 intact negative control rebuilt or quarantined")
        print(json.dumps(intact, indent=2, default=str)[:2000])
        return 1
    if not intact.get("payload_sha256_match"):
        print("FAILED:TST-0097-probe1 intact hash mismatch")
        return 1
    if not ok:
        print(f"FAILED:TST-0097-probe1 {why}")
        print(json.dumps(rows, indent=2, default=str)[:4000])
        return 1
    if not named:
        print("FAILED:TST-0097-probe1 detection mechanism unnamed or unexpected")
        print(json.dumps([{k: r.get(k) for k in ('corruption_mode','detection_mechanism')} for r in rows], indent=2))
        return 1
    if not leftover_ok:
        print("FAILED:TST-0097-probe1 leftover tmp served or not cleared")
        print(json.dumps(leftover, indent=2, default=str)[:2000])
        return 1
    if any(r.get("served_corrupt") for r in rows):
        print("FAILED:TST-0097-probe1 P0 served corrupt")
        return 1

    out = {
        "probe": "probe1-corruption-modes",
        "unit_id": "TST-0097",
        "pass": True,
        "cases": [
            {
                "corruption_mode": r["corruption_mode"],
                "detection_mechanism": r["detection_mechanism"],
                "served_corrupt": r["served_corrupt"],
                "rebuilt": r["rebuilt"],
                "payload_sha256_match": r["payload_sha256_match"],
                "quarantined": r["quarantined"],
                "sibling_intact": r.get("sibling_intact"),
            }
            for r in rows
        ],
        "intact_negative_control": {
            "hit": intact["hit"],
            "quarantined": intact["quarantined"],
            "payload_sha256_match": intact["payload_sha256_match"],
        },
        "p0_silent_serve": False,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "modes="
        + ",".join(r["corruption_mode"] for r in rows)
        + " named_detect=True silent_serve=False sibling_intact=True"
    )
    print("SUCCESS:TST-0097-probe1 each corruption mode detected and rebuilt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
