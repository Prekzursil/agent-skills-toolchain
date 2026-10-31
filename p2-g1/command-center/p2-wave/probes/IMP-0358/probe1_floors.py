#!/usr/bin/env python3
"""IMP-0358 probe1: floor-enforcement matrix across the risk classes.

Live re-run of the catalog evidence: at-floor configs are accepted and every
one-below-floor config is refused, for each of LOW/MODERATE/HIGH/CRITICAL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.risk import (  # noqa: E402
    RiskError,
    at_floor,
    floor_enforcement_matrix,
    map_risk_class,
    matrix_is_sound,
)

RECEIPT = REPO / "command-center/receipts/IMP-0358.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0358-probe1 {msg}")
    return 1


def main() -> int:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    m = floor_enforcement_matrix()
    if sorted(m) != ["CRITICAL", "HIGH", "LOW", "MODERATE"]:
        return fail(f"matrix-classes:{sorted(m)}")
    if not matrix_is_sound(m):
        return fail("matrix-unsound")
    for cls, row in m.items():
        if row["at_floor_accepted"] is not True:
            return fail(f"{cls}:at-floor-rejected")
        if len(row["rejected_dims"]) != 4:
            return fail(f"{cls}:one-below-miss:{row['rejected_dims']}")

    high = map_risk_class("HIGH")
    if high["quorum"] != 5 or high["reviewer_count"] != 2:
        return fail("HIGH-floors-diverged")
    crit = map_risk_class("CRITICAL")
    if crit["evidence_standard"] != "executable-proof-only":
        return fail("CRITICAL-evidence-floor")

    cfg_ok = at_floor(dict(high), "HIGH")
    if not cfg_ok.accepted:
        return fail("at-floor-HIGH-rejected")
    sub = at_floor({"protocol_strength": 2, "quorum": 5,
                    "evidence_standard": "peer-reviewed-only",
                    "reviewer_count": 2}, "HIGH")
    if sub.accepted or sub.deficits != ["protocol_strength"]:
        return fail(f"sub-floor-HIGH:{sub.as_dict()}")

    try:
        map_risk_class("moon-dust")
        return fail("unknown-class-accepted")
    except RiskError:
        pass

    print(json.dumps({
        "probe": "probe1-floors", "unit_id": "IMP-0358", "pass": True,
        "classes": sorted(m), "matrix_sound": True,
        "HIGH_floors": high, "sub_floor_deficits": sub.deficits,
    }, sort_keys=True))
    print("SUCCESS:IMP-0358-probe1 floor matrix sound across LOW/MODERATE/HIGH/CRITICAL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
