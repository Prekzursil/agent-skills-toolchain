#!/usr/bin/env python3
"""Probe 1: live venue recipes + both-states revert detector control.

Independent of probe 2 (which re-hashes lineage and mutates overclaims).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0148-probe1 {msg}")
    return 1


def main() -> int:
    if not E.ARTIFACT.is_file() or E.ARTIFACT.stat().st_size <= 0:
        return fail("artifact missing")
    art = json.loads(E.ARTIFACT.read_text(encoding="utf-8"))
    if art.get("unit_id") != "RES-0148":
        return fail(f"unit_id {art.get('unit_id')}")
    if "SUCCESS:RES-0148" not in json.dumps(art):
        return fail("sentinel-absent")
    st = str(art.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = E.build_document()
    if live.get("state") != "SUCCESS":
        return fail(f"live engine state={live.get('state')}")

    venues = {v["id"]: v for v in live["venues"]}
    want = ["V-WONTFIX", "V-REVERT", "V-RETRACT", "V-MIGRATE", "V-DEPREC", "V-PIR"]
    if list(venues) != want:
        return fail(f"venue ids {list(venues)}")
    for vid, v in venues.items():
        n = len(v.get("examples") or [])
        print(f"venue {vid} status={v['status']} examples={n}")
        if v["status"] != "PRODUCTIVE":
            return fail(f"{vid} not PRODUCTIVE")
        if n < 2:
            return fail(f"{vid} examples={n} want>=2")
        for ex in v["examples"]:
            if not ex["signal_a"]["pass"] or not ex["signal_b"]["pass"]:
                return fail(f"{vid} {ex['id']} missing independent signal")
            if ex["signal_a"]["backend"] == ex["signal_b"]["backend"]:
                return fail(f"{vid} {ex['id']} backends not independent")

    det = live["detector_control"]
    if not det["positive"]["pass"]:
        return fail("detector positive (known revert) did not fire")
    if not det["negative"]["pass"]:
        return fail("detector negative (no revert) was not silent")
    if det["positive"]["grep_hits"] < 1:
        return fail("grep hits on control repo")
    policy = det["zero_verdict_policy"]
    # Detector passed, we have hits on public git/git — zeros are not being accepted here.
    if policy["accept_zero"] is True:
        return fail("zero verdict accepted despite non-zero public yield")
    broken = E.zero_verdict_policy(False, 0)
    if broken["accept_zero"] is not False:
        return fail("zero verdict must be refused when detector fails")

    art_venues = {v["id"]: v["status"] for v in art.get("venues") or []}
    live_venues = {v["id"]: v["status"] for v in live["venues"]}
    if art_venues != live_venues:
        return fail(f"artifact/live venue status drift {art_venues} vs {live_venues}")

    live_urls = sorted(
        e["url"] for v in live["venues"] for e in v["examples"] if e.get("url")
    )
    art_urls = sorted(
        e["url"] for v in art.get("venues") or [] for e in v.get("examples") or [] if e.get("url")
    )
    if live_urls != art_urls:
        return fail("artifact example URLs drifted from live recipes")

    print(
        f"detector_pos={det['positive']['pass']} detector_neg={det['negative']['pass']} "
        f"venues_productive={len(venues)} examples={sum(len(v['examples']) for v in venues.values())}"
    )
    print("SUCCESS:RES-0148-probe1 recipe retrieval and revert detector control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
