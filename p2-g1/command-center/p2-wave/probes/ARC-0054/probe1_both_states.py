#!/usr/bin/env python3
"""Probe 1: both-states per criterion, silent-repair NO-OP, live measurements.

Must fire on the bad live artifact and pass on the rewritten/healthy control
for each of the five catalog-named UX modes. Healthy repair must be NO-OP.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A8/FAILURE-MODES.json"


def main() -> int:
    run = S.both_states(REPO)
    for name, ok in run["checks"].items():
        print(f"{name}={ok}")
    if not run["pass"]:
        print(f"FAILED:ARC-0054-probe1 {run['failed']}")
        return 1

    if not ART.is_file():
        print("FAILED:ARC-0054-probe1 FAILURE-MODES.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0054-probe1 self-declared {doc.get('state')}")
        return 1
    ux = doc.get("ux_criteria") or {}
    for key, val in run["checks"].items():
        if ux.get(key) is not True:
            print(f"FAILED:ARC-0054-probe1 artifact missing {key}")
            return 1
        if bool(val) is not True:
            print(f"FAILED:ARC-0054-probe1 live {key} false")
            return 1
    live = doc.get("live_measurements") or {}
    cat = run["details"]["catalog"]
    if int(live.get("work_unit_count") or 0) != int(cat["n_items"]):
        print("FAILED:ARC-0054-probe1 catalog count drift")
        return 1
    if "SUCCESS:ARC-0054" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0054-probe1 sentinel absent")
        return 1
    print(
        "silent_repair_noop=True "
        f"catalog_n={cat['n_items']} largest={cat['largest_bucket']} "
        f"a8_design={run['details']['a8_design_present']}"
    )
    print("SUCCESS:ARC-0054-probe1 both-states silent-repair live criteria")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
