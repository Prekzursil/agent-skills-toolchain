#!/usr/bin/env python3
"""IMP-0213 probe 2: stored scores recompute from recorded inputs.

Independence: the weighted combine is reimplemented here and is not imported
from the library. Path dimensions are recomputed by calling recommend() on the
recorded inputs (single source of truth for path physics) and compared to the
receipt table. A stored score that does not match either check fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from workflows.path_recommender import Inputs, recommend  # noqa: E402

RECEIPT = REPO / "command-center/receipts/IMP-0213.json"

# Published weights, copied (not imported) so a silent WEIGHTS edit still
# has to match the arithmetic frozen in the receipt.
W_COST = 300
W_LICENCE = 250
W_FIT = 300
W_MAINT = 150


def independent_combine(
    expected_cost: int,
    licence_risk: int,
    capability_fit: int,
    maintenance_burden: int,
) -> int:
    return (
        W_COST * (1000 - expected_cost)
        + W_LICENCE * (1000 - licence_risk)
        + W_FIT * capability_fit
        + W_MAINT * (1000 - maintenance_burden)
    ) // 1000


def main() -> int:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        print("FAILED:IMP-0213-probe2 receipt missing")
        return 1
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    table = doc.get("sensitivity_table") or []
    if len(table) < 3:
        print(f"FAILED:IMP-0213-probe2 sensitivity_table too small: {len(table)}")
        return 1

    mismatches = []
    checked = 0
    for row in table:
        inp = Inputs(**row["inputs"])
        live = recommend(inp)
        stored_rec = row.get("recommendation")
        if live["recommendation"] != stored_rec:
            mismatches.append(
                {
                    "scenario": row.get("scenario"),
                    "kind": "recommendation",
                    "stored": stored_rec,
                    "live": live["recommendation"],
                }
            )
        for path, stored_path in (row.get("paths") or {}).items():
            live_path = live["paths"][path]
            if bool(stored_path.get("eligible")) != bool(live_path.get("eligible")):
                mismatches.append(
                    {
                        "scenario": row.get("scenario"),
                        "path": path,
                        "kind": "eligibility",
                        "stored": stored_path.get("eligible"),
                        "live": live_path.get("eligible"),
                    }
                )
                continue
            if not stored_path.get("eligible"):
                continue
            for key in (
                "expected_cost",
                "licence_risk",
                "capability_fit",
                "maintenance_burden",
                "score",
            ):
                if stored_path.get(key) != live_path.get(key):
                    mismatches.append(
                        {
                            "scenario": row.get("scenario"),
                            "path": path,
                            "kind": key,
                            "stored": stored_path.get(key),
                            "live": live_path.get(key),
                        }
                    )
            stored_score = stored_path["score"]
            recomputed = independent_combine(
                stored_path["expected_cost"],
                stored_path["licence_risk"],
                stored_path["capability_fit"],
                stored_path["maintenance_burden"],
            )
            if recomputed != stored_score:
                mismatches.append(
                    {
                        "scenario": row.get("scenario"),
                        "path": path,
                        "kind": "independent-combine",
                        "stored": stored_score,
                        "recomputed": recomputed,
                    }
                )
            checked += 1

    print(
        json.dumps(
            {
                "probe": "probe2-recompute-scores",
                "unit_id": "IMP-0213",
                "rows": len(table),
                "eligible_path_scores_checked": checked,
                "mismatches": mismatches[:12],
                "n_mismatches": len(mismatches),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if mismatches:
        print(f"FAILED:IMP-0213-probe2 {len(mismatches)} score mismatches")
        return 1
    if checked < 5:
        print(f"FAILED:IMP-0213-probe2 too few eligible scores checked: {checked}")
        return 1
    print(
        f"SUCCESS:IMP-0213-probe2 recomputed {checked} eligible path scores "
        f"from {len(table)} recorded input rows; 0 mismatches"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
