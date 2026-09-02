#!/usr/bin/env python3
"""Probe 1: path-coverage assertion."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from dispatch import FAMILIES  # noqa: E402
from enumerate_paths import sweep  # noqa: E402


def main() -> int:
    report = sweep(include_plant=False)
    cal = report["calibration"]
    print(
        f"calibration found={cal['found']} is_entry={cal['is_entry']} "
        f"calls_choke={cal['calls_choke']} ok={cal['ok']} "
        f"path={cal['rel']}::{cal['qual']}"
    )
    if not cal["ok"]:
        print("FAILED:ARC-0045-probe1 detector missed known-present path")
        return 1

    design = report["design"]
    print(
        f"design enumerated={design['enumerated']} crossing={design['crossing']} "
        f"coverage={design['coverage']:.4f} families={design['families']}"
    )
    if design["enumerated"] < len(FAMILIES) or design["coverage"] != 1.0:
        print("FAILED:ARC-0045-probe1 design wrappers do not all cross the choke")
        return 1
    missing_design = [f for f in FAMILIES if f not in set(design["families"])]
    if missing_design:
        print(f"FAILED:ARC-0045-probe1 design missing families {missing_design}")
        return 1

    live = report["current_tree"]
    print(
        f"live enumerated={live['enumerated']} crossing={live['crossing']} "
        f"families={live['families']}"
    )
    if live["enumerated"] < 1:
        print("FAILED:ARC-0045-probe1 live sweep found no invocation entries")
        return 1
    if live["families_missing_wrapper"]:
        print(
            "FAILED:ARC-0045-probe1 live families without design wrapper "
            f"{live['families_missing_wrapper']}"
        )
        return 1

    cov = report["coverage"]
    print(
        f"coverage enumerated={cov['enumerated']} crossing={cov['crossing']} "
        f"ratio={cov['ratio']:.4f} shortfall={cov['shortfall_count']}"
    )
    live_debt = [row for row in cov["shortfall"] if row.get("source") == "current-tree"]
    print(f"shortfall_itemized live_unwired={len(live_debt)}")
    for row in live_debt[:12]:
        print(
            f"  shortfall {row['rel']}::{row['qual']} family={row['family']} "
            f"reason={row['shortfall_reason']}"
        )
    if not live_debt:
        print("FAILED:ARC-0045-probe1 expected live unwired shortfall on this unmigrated tree")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1",
                "calibration_ok": True,
                "design_coverage": design["coverage"],
                "ratio": cov["ratio"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:ARC-0045-probe1 path-coverage assertion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
