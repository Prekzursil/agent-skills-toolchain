#!/usr/bin/env python3
"""Probe 2: planted-bypass detector control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from enumerate_paths import sweep  # noqa: E402


def main() -> int:
    clean = sweep(include_plant=False)
    planted = sweep(include_plant=True)
    mutant = sweep(include_plant=True, mutant_blind=True)

    design_bypass_clean = [
        r for r in clean["coverage"]["shortfall"] if r.get("source") == "design"
    ]
    plant_found = planted["plant"]["found"]
    plant_rows = planted["plant"]["rows"]
    mutant_found = mutant["plant"]["found"]

    print(
        f"clean design_shortfall={len(design_bypass_clean)} "
        f"plant_found={plant_found} plant_rows={len(plant_rows)} "
        f"mutant_found={mutant_found}"
    )
    if design_bypass_clean:
        print("FAILED:ARC-0045-probe2 design wrappers bypass the choke")
        return 1
    if not plant_found or not plant_rows:
        print("FAILED:ARC-0045-probe2 planted bypass not found")
        return 1
    reasons = {r.get("shortfall_reason") for r in plant_rows}
    if "planted-bypass" not in reasons:
        print(f"FAILED:ARC-0045-probe2 plant reason {reasons}")
        return 1
    if mutant_found:
        print("FAILED:ARC-0045-probe2 mutant still saw the plant; detector is not doing the work")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe2",
                "fired_on_plant": True,
                "silent_on_clean_design": True,
                "mutant_misses_plant": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:ARC-0045-probe2 planted-bypass detector control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
