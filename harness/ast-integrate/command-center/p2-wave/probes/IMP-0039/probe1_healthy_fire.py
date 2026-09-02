#!/usr/bin/env python3
"""Named probe 1: healthy hooks.json — hook actually fires (two independent signals)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

from hook_fire_probe import run_probe  # noqa: E402

HEALTHY = HERE / "fixtures" / "healthy"


def main() -> int:
    report = run_probe(HEALTHY, work_dir=HERE / ".work" / "probe1")
    print(json.dumps(report.to_dict(), sort_keys=True))
    if report.verdict != "FIRED":
        print("FAILED:IMP-0039-probe1 expected FIRED on healthy config")
        return 1
    if not report.sentinel_observed:
        print("FAILED:IMP-0039-probe1 sentinel not observed after trigger")
        return 1
    if report.hook_id not in report.inventory_loaded:
        print("FAILED:IMP-0039-probe1 inventory did not list the hook as loaded")
        return 1
    if report.trigger_count < 1:
        print("FAILED:IMP-0039-probe1 trigger did not run a loaded hook")
        return 1
    print("SUCCESS:IMP-0039-probe1 healthy FIRED sentinel+inventory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
