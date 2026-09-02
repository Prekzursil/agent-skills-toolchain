#!/usr/bin/env python3
"""Named probe 1: deleting a known test moves its requirement into the untested set."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import DELETE_REQ, control_delete_moves_untested  # noqa: E402
from corpus import fixture_requirements, fixture_tests  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0043.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:BLD-0043-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "BLD-0043":
        print("FAILED:BLD-0043-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:BLD-0043" not in ART.read_text(encoding="utf-8"):
        print("FAILED:BLD-0043-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:BLD-0043-probe1 self-declared", doc.get("state"))
        return 1

    ctrl = control_delete_moves_untested(fixture_requirements(), fixture_tests())
    recorded = [
        c for c in (doc.get("controls") or []) if c.get("id") == ctrl["id"]
    ]
    if not ctrl["pass"]:
        print("FAILED:BLD-0043-probe1 control did not pass")
        print(json.dumps(ctrl, indent=2)[:2000])
        return 1
    if not recorded or recorded[0].get("pass") is not True:
        print("FAILED:BLD-0043-probe1 receipt missing passing delete control")
        return 1

    live_untested = {u.get("id") for u in doc.get("untested_requirements") or []}
    payload = {
        "probe": "probe1-delete-untested",
        "unit_id": "BLD-0043",
        "pass": True,
        "removed_tests": ctrl.get("removed_tests"),
        "requirement": DELETE_REQ,
        "live_untested_count": len(live_untested),
        "receipt_control_pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"removed={ctrl.get('removed_tests')} "
        f"req={DELETE_REQ} moved_to_untested=True"
    )
    print("SUCCESS:BLD-0043-probe1 delete-known-test-moves-untested")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
