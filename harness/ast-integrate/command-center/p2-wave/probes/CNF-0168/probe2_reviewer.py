#!/usr/bin/env python3
"""Named probe 2: reviewer plants one fault per direction; live counts re-derived."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0168.json"


def main() -> int:
    plants = A.reviewer_plants()
    if not plants.get("pass"):
        print("FAILED:CNF-0168-probe2 reviewer plants did not fire both directions")
        print(json.dumps(plants, indent=2, default=str)[:4000])
        return 1
    print(
        "reviewer_plants "
        f"A={plants.get('direction_a_fires_on_truncate')} "
        f"B={plants.get('direction_b_fires_on_complete_without_sentinel')}"
    )

    if not ART.is_file():
        print("FAILED:CNF-0168-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in A.NOT_DELIVERING:
        print(f"FAILED:CNF-0168-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNF-0168" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0168-probe2 sentinel absent")
        return 1

    live = A.live_census(REPO)
    dirs = A.directions_of(doc)
    art_a = dirs.get("sentinel_on_incomplete") or {}
    art_b = dirs.get("complete_without_sentinel") or {}
    live_a = live["direction_a_sentinel_on_incomplete"]
    live_b = live["direction_b_complete_without_sentinel"]
    if int(art_a.get("count", -1)) != int(live_a["count"]):
        print(
            f"FAILED:CNF-0168-probe2 Direction A count drift "
            f"artifact={art_a.get('count')} live={live_a['count']}"
        )
        return 1
    if int(art_b.get("count", -1)) != int(live_b["count"]):
        print(
            f"FAILED:CNF-0168-probe2 Direction B count drift "
            f"artifact={art_b.get('count')} live={live_b['count']}"
        )
        return 1
    if list(art_a.get("ids") or []) != list(live_a["ids"]):
        print("FAILED:CNF-0168-probe2 Direction A id-list drift")
        return 1
    if list(art_b.get("ids") or []) != list(live_b["ids"]):
        print("FAILED:CNF-0168-probe2 Direction B id-list drift")
        return 1
    if "combined_count" in dirs or "sentinel_mismatch" in doc:
        print("FAILED:CNF-0168-probe2 combined mismatch number present")
        return 1
    if "combined_count" in (doc.get("report") or {}):
        print("FAILED:CNF-0168-probe2 combined mismatch number present in report")
        return 1

    own = A.classify_path(
        ART,
        unit_id="CNF-0168",
        declared="SUCCESS:CNF-0168",
    )
    if own["direction"] != "healthy":
        print(f"FAILED:CNF-0168-probe2 own receipt classified {own['direction']}")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("verdict") != "PASS" or not rev.get("independent"):
        print("FAILED:CNF-0168-probe2 reviewer block missing independent PASS")
        return 1
    plants_doc = A.plants_of(doc)
    if plants_doc.get("direction_a") != "truncated-with-sentinel":
        print("FAILED:CNF-0168-probe2 reviewer A plant not recorded")
        return 1
    if plants_doc.get("direction_b") != "complete-without-sentinel":
        print("FAILED:CNF-0168-probe2 reviewer B plant not recorded")
        return 1

    print(
        f"live_A={live_a['count']} live_B={live_b['count']} "
        f"healthy={live['healthy_count']} own=healthy"
    )
    print("SUCCESS:CNF-0168-probe2 reviewer-plants live two-counts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
