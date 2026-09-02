#!/usr/bin/env python3
"""Named probe 2: static audit — production tree clean; planted lifecycle call is found."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.audit import detect_plant, private_material_hits, scan_tree  # noqa: E402
from marketplace.custody import POLICY, CustodyViolation, refuse_lifecycle  # noqa: E402

MARKET = REPO / "tools" / "marketplace"
PLANT = (
    "def rotate_key(kid):\n"
    "    return kid\n"
    "\n"
    "rsa.generate_private_key(public_exponent=65537, key_size=2048)\n"
)


def main() -> int:
    production = scan_tree(MARKET)
    planted = detect_plant(PLANT)
    secrets = private_material_hits(MARKET)
    refused = False
    try:
        refuse_lifecycle("rotate")
    except CustodyViolation:
        refused = True

    plant_names = sorted({h.name for h in planted})
    plant_found = any("rotate_key" in n for n in plant_names) and any(
        "generate_private_key" in n for n in plant_names
    )
    report = {
        "probe": "probe2-lifecycle-audit",
        "unit_id": "IMP-0075",
        "production_hits": [h.__dict__ for h in production],
        "production_hit_count": len(production),
        "plant_hit_count": len(planted),
        "plant_names": plant_names,
        "plant_found": plant_found,
        "private_material_hits": secrets,
        "custody_holder": POLICY["holder"],
        "lifecycle_refused": refused,
        "non_vacuous": plant_found,
        "pass": False,
    }
    ok = (
        production == []
        and plant_found
        and secrets == []
        and refused
        and POLICY["holder"] == "owner"
        and POLICY["program_role"] == "consume-and-window-check-only"
    )
    report["pass"] = ok
    print(json.dumps(report, sort_keys=True))
    print(
        f"production_hits={len(production)} plant_found={plant_found} "
        f"secrets={len(secrets)} lifecycle_refused={refused}"
    )
    if not ok:
        print("FAILED:IMP-0075-probe2 lifecycle audit")
        return 1
    print("SUCCESS:IMP-0075-probe2 production clean and planted call detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
