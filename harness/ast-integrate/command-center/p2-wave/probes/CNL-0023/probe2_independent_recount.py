#!/usr/bin/env python3
"""Probe 2: independent recount from fixtures, not from the author's argument.

Re-tabulates equal / justified-non-equal / unjustified seats with recount.py
(does not import validator.py). A disagreement with the numbers published in
the design note blocks the unit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import recount as R  # noqa: E402

UID = "CNL-0023"
ART = (
    HERE.parents[3]
    / "command-center/design/council/CNL-0023-vote-rights-and-the-provenance-of-every-non-equal-weight.md"
)


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("design artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:CNL-0023" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")

    live_good = R.recount_fixture("known-good.json")
    live_bad = R.recount_fixture("planted-bad.json")
    print(
        f"recount good seats={live_good['seats']} equal={live_good['equal_weight']} "
        f"justified={live_good['justified_non_equal']} unjustified={live_good['unjustified_count']}"
    )
    print(
        f"recount bad seats={live_bad['seats']} unjustified={live_bad['unjustified_count']} "
        f"ids={live_bad['unjustified_seat_ids']} whys={[row['why'] for row in live_bad['unjustified']]}"
    )
    if live_good["unjustified_count"] != 0 or live_good["justified_non_equal"] != 3:
        return fail("known-good recount drifted")
    if live_bad["unjustified_count"] != 3:
        return fail("planted-bad recount did not find 3 unjustified seats")
    if live_bad["unjustified_seat_ids"] != [
        "seat.expert-unjustified",
        "seat.expert-label",
        "seat.tampered-digest",
    ]:
        return fail(f"unexpected bad seats {live_bad['unjustified_seat_ids']}")

    pub = doc.get("reviewer_recount") or {}
    for key in ("equal_weight", "justified_non_equal", "unjustified_count"):
        if pub.get("known_good", {}).get(key) != live_good[key]:
            return fail(f"published known_good.{key} disagrees with live recount")
        if key == "unjustified_count" and pub.get("planted_bad", {}).get(key) != live_bad[key]:
            return fail("published planted_bad.unjustified_count disagrees with live recount")
        if key != "unjustified_count" and pub.get("planted_bad", {}).get(key) != live_bad.get(key):
            return fail(f"published planted_bad.{key} disagrees with live recount")
    if pub.get("planted_bad", {}).get("unjustified_seat_ids") != live_bad["unjustified_seat_ids"]:
        return fail("published unjustified_seat_ids disagrees with live recount")
    if pub.get("independent") is not True:
        return fail("reviewer_recount.independent is not true")
    if pub.get("method") != "recount.py over fixtures, not the author's narrative":
        return fail("reviewer method missing")

    print("SUCCESS:CNL-0023-probe2 independent recount agrees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
