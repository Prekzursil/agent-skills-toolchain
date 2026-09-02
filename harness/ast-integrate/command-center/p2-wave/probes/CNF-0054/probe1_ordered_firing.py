#!/usr/bin/env python3
"""Probe 1: live ordered firing lists before and after, plus set difference.

Inventory comes from the execution log of a scripted session. Manifest
membership is not consulted when building the fired set.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import inventory as inv  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0054-hook-firing-diff.json"


def main() -> int:
    m = inv.measure()
    before = m["before"]
    after = m["after"]
    delta = m["primary_delta"]
    print(
        json.dumps(
            {
                "probe": "probe1-ordered-firing",
                "unit_id": "CNF-0054",
                "before_firing_count": before["firing_count"],
                "after_firing_count": after["firing_count"],
                "before_ordered": [
                    {"seq": r["seq"], "hook_id": r["hook_id"], "event": r["event"], "exit_code": r["exit_code"]}
                    for r in before["ordered_firing"]
                ],
                "after_ordered": [
                    {"seq": r["seq"], "hook_id": r["hook_id"], "event": r["event"], "exit_code": r["exit_code"]}
                    for r in after["ordered_firing"]
                ],
                "missing_from_after": delta["missing_from_after"],
                "any_hook_missing_from_after": delta["any_hook_missing_from_after"],
                "source": "execution-log",
            },
            sort_keys=True,
        )
    )
    if before["firing_count"] < 7 or after["firing_count"] < 7:
        print("FAILED:CNF-0054-probe1 under-firing")
        return 1
    if delta["any_hook_missing_from_after"]:
        print("FAILED:CNF-0054-probe1 unexpected missing", delta["missing_from_after"])
        return 1
    # Manifest must not be used as the fired set: every fired id was subprocessed.
    for rec in before["ordered_firing"] + after["ordered_firing"]:
        if rec.get("source") != "execution-log":
            print("FAILED:CNF-0054-probe1 source is not execution-log")
            return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0054-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0054-probe1 self-declared", doc.get("state"))
        return 1
    if inv.SENTINEL not in text:
        print("FAILED:CNF-0054-probe1 sentinel absent")
        return 1
    view = inv.artifact_view(doc)
    art_before = (view.get("before") or {}).get("ordered_firing") or []
    art_after = (view.get("after") or {}).get("ordered_firing") or []
    if len(art_before) != before["firing_count"] or len(art_after) != after["firing_count"]:
        print("FAILED:CNF-0054-probe1 artifact firing-list length drift")
        return 1
    live_ids_b = [r["hook_id"] for r in before["ordered_firing"]]
    art_ids_b = [r["hook_id"] for r in art_before]
    live_ids_a = [r["hook_id"] for r in after["ordered_firing"]]
    art_ids_a = [r["hook_id"] for r in art_after]
    if live_ids_b != art_ids_b or live_ids_a != art_ids_a:
        print("FAILED:CNF-0054-probe1 artifact ordered ids != live")
        return 1
    print("SUCCESS:CNF-0054-probe1 ordered firing lists and set difference")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
