#!/usr/bin/env python3
"""Probe 1: same frozen lockfile against two dated advisory snapshots.

Requires a GREEN→RED verdict change with GHSA-9wx4-h78v-vm56 appearing,
no package-bit change, and the prompt payload remaining unscannable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scan as S  # noqa: E402

UNIT = "RES-0051"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    cmp = S.two_snapshot_comparison()
    print(
        json.dumps(
            {
                "probe": "probe1-two-snapshot",
                "unit_id": UNIT,
                "verdict_a": cmp["verdict_a"],
                "verdict_b": cmp["verdict_b"],
                "verdict_changed": cmp["verdict_changed"],
                "appeared_ids": cmp["appeared_ids"],
                "snapshot_a": cmp["snapshot_a"],
                "snapshot_b": cmp["snapshot_b"],
                "unscannable_both": cmp["unscannable_both"],
                "node_still_green_at_b": cmp["node_still_green_at_b"],
                "pass": cmp["pass"],
            },
            sort_keys=True,
        )
    )
    if not cmp["pass"]:
        return fail("two-snapshot comparison did not GREEN→RED on GHSA-9wx4-h78v-vm56")
    if cmp["scan_a"]["hit_count"] != 0:
        return fail(f"snapshot A not green hits={cmp['scan_a']['hits']}")
    if S.HIT_ID not in cmp["appeared_ids"]:
        return fail(f"expected {S.HIT_ID} to appear")
    if not cmp["unscannable_both"]:
        return fail("prompt payload was not unscannable on both snapshots")
    if not cmp["node_still_green_at_b"]:
        return fail("cross-spawn flipped at B; GHSA-3xgq must still be unpublished")

    art_path = S.artifact_path()
    if not art_path.is_file() or art_path.stat().st_size <= 0:
        return fail("research artifact missing")
    text = art_path.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    sentinel = S.catalog_sentinel()
    if sentinel not in text:
        return fail("catalog completion_sentinel absent from artifact")
    recorded = doc.get("two_snapshot_scan") or {}
    if recorded.get("verdict_a") != "GREEN" or recorded.get("verdict_b") != "RED":
        return fail("artifact two_snapshot_scan verdicts drifted")
    if S.HIT_ID not in (recorded.get("appeared_ids") or []):
        return fail("artifact did not record the appearing advisory")
    print(
        f"A={cmp['verdict_a']} B={cmp['verdict_b']} appeared={cmp['appeared_ids']} "
        f"unscannable_both={cmp['unscannable_both']}"
    )
    print("SUCCESS:RES-0051-probe1 two-snapshot scan comparison GREEN→RED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
