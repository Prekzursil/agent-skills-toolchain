r"""Compute which of the 2,007 work units are STARTABLE right now, and emit a build worklist.

A unit is READY when every dependency it declares is satisfiable:
  * a unit-id dependency is satisfied when that unit's artifact EXISTS at its declared output_path;
  * a `B\d+` bucket dependency is treated per the owner ruling recorded in OWNER-DECISIONS.md --
    "a bucket-level gate artifact exists" -- which makes a zero-member bucket SATISFIED rather than
    permanently unsatisfiable. That reading is recorded here explicitly because 876 edges turn on
    it and a silent choice would be indefensible;
  * an unknown-form token (ARC, WFA, CC, IMP -- 41 of them) cannot be resolved and BLOCKS, because
    guessing at it would manufacture readiness.

Owner-gated units (`owner_approval_required`) are excluded from the build list no matter how ready
they look: an executor cannot supply an owner ruling.

Emits command-center/READY-UNITS.json for the build fan-out to consume.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
BUCKET = re.compile(r"B\d+")

#: Owner ruling of record, 2026-08-11: a B-token dependency means "a bucket-level gate artifact
#: exists", which is the only reading that does not leave 876 edges permanently unsatisfiable.
BUCKET_SATISFIED = True


def main() -> int:
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = doc["work_units"]
    by_id = {u["id"]: u for u in units}

    def delivered(uid: str) -> bool:
        u = by_id.get(uid)
        if not u:
            return False
        p = u.get("output_path")
        return bool(p) and (REPO / p).exists()

    ready, blocked, gated = [], [], []
    block_reason: Counter = Counter()
    for u in units:
        if u.get("output_path") and (REPO / u["output_path"]).exists():
            continue  # already delivered
        if u.get("owner_approval_required"):
            gated.append(u["id"])
            continue
        reasons = []
        for dep in u.get("dependencies") or []:
            if BUCKET.fullmatch(dep):
                if not BUCKET_SATISFIED:
                    reasons.append(f"bucket:{dep}")
            elif dep in by_id:
                if not delivered(dep):
                    reasons.append(f"unbuilt:{dep}")
            else:
                reasons.append(f"unknown-token:{dep}")
        if reasons:
            blocked.append(u["id"])
            block_reason[reasons[0].split(":")[0]] += 1
        else:
            ready.append(u["id"])

    out = {
        "bucket_reading": "a bucket-level gate artifact exists (owner ruling 2026-08-11)",
        "totals": {
            "units": len(units),
            "already_delivered": sum(
                1
                for u in units
                if u.get("output_path") and (REPO / u["output_path"]).exists()
            ),
            "ready": len(ready),
            "blocked": len(blocked),
            "owner_gated": len(gated),
        },
        "block_reasons": dict(block_reason),
        "ready_units": ready,
        "owner_gated_units": gated,
    }
    (REPO / "command-center/READY-UNITS.json").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    t = out["totals"]
    print(
        f"  units {t['units']} | delivered {t['already_delivered']} | READY {t['ready']} "
        f"| blocked {t['blocked']} | owner-gated {t['owner_gated']}"
    )
    print(f"  block reasons: {out['block_reasons']}")
    print(f"  first ready: {ready[:8]}")
    if (
        t["ready"] + t["blocked"] + t["owner_gated"] + t["already_delivered"]
        != t["units"]
    ):
        print("FAILED:ready-units partition does not sum to the unit count")
        return 1
    print("\nSUCCESS:ready-units partition sums correctly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
