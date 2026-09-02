#!/usr/bin/env python3
"""Named probe 1: fixture publishers match a hand-derived expectation.

Signal 1 is a three-way equality: library output, independent integer oracle
(hand_derive.py, not an import of trust_levels), and the frozen arithmetic
table in tools/marketplace/fixtures/trust_publishers.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

from hand_derive import recompute  # noqa: E402
from trust_levels import (  # noqa: E402
    LEVEL_UNRATED,
    component_map,
    compute_publisher_trust,
)

FIXTURE = REPO / "tools/marketplace/fixtures/trust_publishers.json"
RECEIPT = REPO / "command-center/receipts/IMP-0076.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0076-probe1 {msg}")
    return 1


def main() -> int:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0076":
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if "SUCCESS:IMP-0076" not in text:
        return fail("sentinel-absent")

    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = []
    for item in data["publishers"]:
        rec = item["record"]
        lib = compute_publisher_trust(rec)
        oracle = recompute(rec)
        hand = item["hand_derived"]
        cmap = component_map(lib)
        row = {
            "id": item["id"],
            "lib_level": lib.level,
            "lib_score": lib.score_millipoints,
            "oracle_level": oracle["level"],
            "oracle_score": oracle["score_millipoints"],
            "hand_level": hand["level"],
            "hand_score": hand["score_millipoints"],
            "match": (
                lib.level == oracle["level"] == hand["level"]
                and lib.score_millipoints == oracle["score_millipoints"] == hand["score_millipoints"]
            ),
        }
        if not row["match"]:
            print(json.dumps(row, indent=2))
            return fail(f"three-way mismatch {item['id']}")
        for name, key in (
            ("signed_releases", "signed_mp"),
            ("conformance_pass_rate", "conformance_mp"),
            ("advisory_response_time", "advisory_mp"),
            ("provenance_completeness", "provenance_mp"),
        ):
            if key in hand:
                if cmap[name].millipoints != hand[key] or oracle[key] != hand[key]:
                    return fail(f"component mismatch {item['id']} {name}")
        rows.append(row)

    unrated = [r for r in rows if r["id"] == "unrated-empty"][0]
    if unrated["lib_level"] != LEVEL_UNRATED:
        return fail("empty publisher was not UNRATED")
    if unrated["lib_level"] == "DEFAULT-TRUSTED":
        return fail("DEFAULT-TRUSTED emitted")

    summary = {
        "probe": "probe1-hand-derived",
        "unit_id": "IMP-0076",
        "publishers": len(rows),
        "three_way_matches": sum(1 for r in rows if r["match"]),
        "unrated_empty": unrated["lib_level"],
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    for r in rows:
        print(
            f"fixture {r['id']} level={r['lib_level']} "
            f"mp={r['lib_score']} three_way={r['match']}"
        )
    print("SUCCESS:IMP-0076-probe1 hand-derived fixture match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
