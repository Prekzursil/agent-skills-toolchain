#!/usr/bin/env python3
"""Named probe 2: intentional-removal control + wholesale detector.

Field: presence/absence of the N-only shipped path after set-difference,
and whether wholesale snapshot restore destroys user data. Different field
from probe 1 (sha256 identity of seeded user items).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from checks import live_both_engines  # noqa: E402
from scenario import N_ONLY_REL, PLUGIN  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0042-rollback-user-data.json"
N_ONLY_PROFILE_REL = f"{PLUGIN}/{N_ONLY_REL}"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0042-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0042":
        print("FAILED:CNF-0042-probe2 unit_id", doc.get("unit_id"))
        return 1

    with tempfile.TemporaryDirectory(prefix="cnf0042-p2-") as tmp:
        sd, wh = live_both_engines(Path(tmp) / "work")

    removal = sd["removal"]
    destruction = wh["destruction"]
    if removal.get("vacuous"):
        print("FAILED:CNF-0042-probe2 removal control vacuous (N-only absent before)")
        return 1
    if not removal.get("passed"):
        print("FAILED:CNF-0042-probe2 N-only path still present after rollback")
        print(json.dumps(removal, indent=2))
        return 1
    if not destruction.get("passed") or not destruction.get("destroyed_user_paths"):
        print("FAILED:CNF-0042-probe2 wholesale did not destroy user data")
        print(json.dumps(destruction, indent=2))
        return 1

    rec_removal = doc.get("intentional_removal") or {}
    if rec_removal.get("path") != N_ONLY_PROFILE_REL:
        print("FAILED:CNF-0042-probe2 artifact removal path drift")
        return 1
    if rec_removal.get("present_after") is not False:
        print("FAILED:CNF-0042-probe2 artifact claims N-only still present")
        return 1
    if rec_removal.get("vacuous"):
        print("FAILED:CNF-0042-probe2 artifact removal marked vacuous")
        return 1

    controls = doc.get("controls") or []
    wholesale = next(
        (c for c in controls if c.get("id") == "wholesale-snapshot-negative-control"),
        None,
    )
    if not wholesale or not wholesale.get("passed") or not wholesale.get("discriminates"):
        print("FAILED:CNF-0042-probe2 artifact missing wholesale detector")
        return 1

    out = {
        "probe": "probe2-removal-control",
        "unit_id": "CNF-0042",
        "n_only_path": N_ONLY_PROFILE_REL,
        "removed": True,
        "vacuous": False,
        "wholesale_destroyed_user_paths": destruction["destroyed_user_paths"],
        "wholesale_discriminates": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"removed={N_ONLY_PROFILE_REL} vacuous=False "
        f"wholesale_destroyed={len(destruction['destroyed_user_paths'])}"
    )
    print("SUCCESS:CNF-0042-probe2 intentional removal and wholesale detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
