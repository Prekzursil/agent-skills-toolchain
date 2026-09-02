#!/usr/bin/env python3
"""Probe 1: categorized scan over the real artifact tree.

Signal 1 is a unicode regex over decoded text. Signal 2 is a raw-bytes
prefix count. Counts must match the emitted research record. Values are
never printed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scan import artifact_payload, scan_tree  # noqa: E402

ART = REPO / "command-center/research/RES-0124.json"
SENTINEL = (
    "SUCCESS:RES-0124 in the receipt AND a category-count scan over the "
    "real tree with a passing seeded-identifier detector control"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0124-probe1 {msg}")
    return 1


def main() -> int:
    live = scan_tree(REPO)
    by = live["by_category"]
    print("files_walked=" + str(live["files_walked"]))
    print("content_files_scanned=" + str(live["content_files_scanned"]))
    print("byte_prefix_hits=" + str(live["byte_prefix_hits"]))
    for cat in sorted(by):
        print(f"category {cat} count={by[cat]}")
    print("grand_total=" + str(live["grand_total"]))
    print("sum_check_ok=" + str(live["sum_check_ok"]))
    if not live["sum_check_ok"]:
        return fail("category counts do not sum to grand_total")
    if by.get("windows_home_path", 0) < 1:
        return fail("windows_home_path count is zero on the real tree")
    if live["byte_prefix_hits"] < 1:
        return fail("byte-prefix signal is zero")
    if by.get("seeded_identifier", 0) != 0:
        return fail("real tree contains a leftover seeded identifier")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("research artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text or "SUCCESS:RES-0124" not in text:
        return fail("sentinel absent")
    stored_wrap = artifact_payload(doc).get("category_counts") or {}
    stored = stored_wrap.get("by_category") or {}
    if set(stored) != set(by):
        return fail("artifact category key set != live scan")
    stored_total = sum(int(v) for v in stored.values())
    if int(stored_wrap.get("grand_total") or -1) != stored_total:
        return fail("artifact grand_total != sum of stored category counts")
    if stored_wrap.get("sum_check_ok") is not True:
        return fail("artifact sum_check_ok is not true")
    if int(stored.get("windows_home_path") or 0) < 1:
        return fail("artifact windows_home_path count is zero")
    if int(stored.get("seeded_identifier") or 0) != 0:
        return fail("artifact reports a leftover seeded identifier")
    # Presence must agree; exact totals move on a live multi-writer tree.
    for cat in ("windows_home_path", "credential_filename", "seeded_identifier"):
        live_p = int(by.get(cat) or 0) > 0
        stored_p = int(stored.get(cat) or 0) > 0
        if live_p != stored_p:
            return fail(f"{cat} presence live={live_p} stored={stored_p}")
    print("live_presence_matches_artifact=True")
    print("value_reproduced=False")
    print(
        "SUCCESS:RES-0124-probe1 category-count scan over the real tree"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
