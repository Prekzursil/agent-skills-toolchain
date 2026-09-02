#!/usr/bin/env python3
"""IMP-0468 probe 2: non-case-distinct keys are not reported; receipt is honest.

Independent of probe 1's fixture walk: re-runs the shipped scan and checks the
catalog receipt's collision count, sentinel, and planted-control record.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import case_collision as cc  # noqa: E402

FIX = HERE / "fixtures"
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0468.json"
SENTINEL = "SENTINEL:IMP-0468:CASE-COLLISION-SCANNED"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0468-probe2 {msg}")
    return 1


def main() -> int:
    non_case = cc.detect_file(FIX / "non-case-distinct.json", repo=HERE)
    if not non_case["parse_ok"]:
        return fail(f"non-case unreadable {non_case['error']}")
    if non_case["walk_hits"]:
        return fail(
            "keys that differ by more than case were reported: "
            + json.dumps(non_case["walk_hits"])
        )

    # Adjacent but not case-equal: name/names, id/idx, NameTag.
    obj = json.loads((FIX / "non-case-distinct.json").read_text(encoding="utf-8"))
    folded = [k.casefold() for k in obj]
    if len(folded) != len(set(folded)):
        return fail("fixture itself case-collides; control is invalid")

    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        return fail("catalog receipt absent")
    text = RECEIPT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"receipt-unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("receipt-not-object")
    state = str(doc.get("state") or "").upper()
    if state in NOT_DELIVERING:
        return fail(f"self-declared:{state}")

    live = cc.scan_shipped(REPO)
    if live["signal_disagreement_files"]:
        return fail(f"signal disagreement {live['signal_disagreement_files']}")
    claimed = doc.get("report") or {}
    if not isinstance(claimed, dict):
        return fail("report-missing")
    if claimed.get("collision_count") != live["collision_count"]:
        return fail(
            f"collision_count receipt={claimed.get('collision_count')} "
            f"live={live['collision_count']}"
        )
    if claimed.get("files_scanned_count") != live["files_scanned_count"]:
        return fail(
            f"files_scanned_count receipt={claimed.get('files_scanned_count')} "
            f"live={live['files_scanned_count']}"
        )

    collisions = claimed.get("collisions")
    if not isinstance(collisions, list) or len(collisions) != live["collision_count"]:
        return fail("collision list length mismatch")
    for hit in collisions:
        if not isinstance(hit, dict):
            return fail("collision row not object")
        if not hit.get("file") or not isinstance(hit.get("keys"), list):
            return fail(f"collision row missing file/keys {hit}")
        if len(hit["keys"]) < 2:
            return fail(f"collision row lacks both keys {hit}")
        values = hit.get("values")
        if not isinstance(values, dict):
            return fail(f"collision row missing values {hit}")
        for key in hit["keys"]:
            if key not in values:
                return fail(f"value missing for key {key}")

    if live["collision_count"] == 0:
        planted = doc.get("negative_controls") or []
        fired = [
            c
            for c in planted
            if isinstance(c, dict)
            and c.get("fired_on_bad_state") is True
            and c.get("silent_on_good_state") is True
        ]
        if not fired:
            return fail("zero-result-unverified-detector (planted control not recorded)")
        if not claimed.get("canonical_absent"):
            return fail("zero-result must disclose absent canonical product manifests")

    print(
        json.dumps(
            {
                "non_case_hits": 0,
                "live_collision_count": live["collision_count"],
                "live_files_scanned": live["files_scanned_count"],
                "receipt_matches_live_scan": True,
                "canonical_absent": live["canonical_absent"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0468-probe2 non-case-distinct silent and receipt honest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
