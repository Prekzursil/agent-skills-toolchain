"""The lane's four DoD items, re-derived first-hand from COMMITTED blobs at HEAD.

Not cited from a prior round and not read through the lane's own producer: this opens the
committed artifact and the committed receipts directly. A round that ends by quoting an earlier
round's DoD table has verified nothing.

Run:  python command-center/p2-next/_k3_dod.py
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ART = "command-center/p2-next/VENDOR-SATISFIABILITY.json"


def blob(rel: str) -> str:
    out = subprocess.run(
        ["git", "show", f"HEAD:{rel}"], cwd=REPO, capture_output=True, check=True
    )
    return out.stdout.decode("utf-8", "replace")


def main() -> int:
    rows = json.loads(blob(ART))["units"]
    verdicts = Counter(r["verdict"] for r in rows)
    req = sum(1 for r in rows if (r.get("reviewer_requirement") or "").strip())
    blocked_on = sum(1 for r in rows if (r.get("blocked_on") or "").strip())
    print(
        f"DoD1 rows={len(rows)} unique_ids={len({r['id'] for r in rows})} {dict(verdicts)}"
    )
    print(
        f"DoD2 non-empty reviewer_requirement {req}/{len(rows)}; blocked_on {blocked_on}/{len(rows)}"
    )

    sat = [r for r in rows if r["verdict"] == "SATISFIABLE_NOW"]
    ok, lens, vendors = 0, [], Counter()
    for r in sat:
        rec = json.loads(blob(r["output_path"]))
        rv = rec.get("reviewer") or {}
        notes = rv.get("notes") or ""
        lens.append(len(notes))
        vendors[(rv.get("reviewer_id") or "?").lower()[:24]] += 1
        if rv.get("verdict") == "PASS" and rv.get("independent") is True:
            ok += 1
    print(
        f"DoD3 satisfiable={len(sat)} reviewed_PASS_independent={ok} notes {min(lens)}-{max(lens)} chars"
    )

    rail = [r for r in rows if r["verdict"] == "RAIL_BLOCKED"]
    unfulfilled = sum(1 for r in rail if r.get("still_needs_cross_vendor"))
    fulfilled = sum(1 for r in rail if r.get("cross_vendor_fulfilled"))
    print(
        f"DoD4 rail_blocked={len(rail)} still_owed={unfulfilled} already_served={fulfilled}"
    )

    # CONTROL: the same reader over the SATISFIABLE population must find ZERO cross-vendor
    # fulfilment. If it returned a number there too, it would be counting "has a reviewer" and
    # the 39/3 split would be an artifact of the reader rather than a property of the receipts.
    sat_fulfilled = sum(1 for r in sat if r.get("cross_vendor_fulfilled"))
    control = fulfilled > 0 and sat_fulfilled == 0
    print(
        f"CONTROL fulfilment counter separates the populations: {control} (satisfiable fulfilled={sat_fulfilled})"
    )

    partition = fulfilled + unfulfilled == len(rail)
    good = (
        len(rows) == len({r["id"] for r in rows})
        and req == len(rows)
        and ok == len(sat)
        and partition
        and control
    )
    print("SUCCESS:k3-dod" if good else "FAILED:k3-dod a DoD item did not hold")
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
