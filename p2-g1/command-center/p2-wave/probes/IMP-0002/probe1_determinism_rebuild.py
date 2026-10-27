#!/usr/bin/env python3
"""Named probe 1 (IMP-0002): live determinism rebuild + recorded-campaign consistency.

Rebuilds the pack fixture twice through pack.pack_repository in THIS run and
requires byte-identical archives (the unit's core claim). Also checks the
receipt's recorded campaign self-consistency (build1==build2==build3==
independent-hasher digest). The receipt's recorded digest was taken against a
fixture that was later simplified; digest equality across TIME is explicitly
NOT asserted here - determinism (equality within the run) is.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
TESTS = TOOLS / "plugin" / "tests"
for p in (TOOLS, TESTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from test_pack_determinism import (  # noqa: E402
    test_two_builds_identical,
)

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0002.json"
UNIT = "IMP-0002"


def main() -> int:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        print(f"FAILED:{UNIT}-probe1 receipt missing")
        return 1
    text = RECEIPT.read_text(encoding="utf-8")
    if f"SUCCESS:{UNIT}" not in text:
        print(f"FAILED:{UNIT}-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:{UNIT}-probe1 self-declared {st}")
        return 1
    rev = doc.get("reviewer") or {}
    if not (rev.get("verdict") == "PASS" and rev.get("independent") is True):
        print("FAILED:IMP-0002-probe1 receipt reviewer closure absent")
        return 1

    live = test_two_builds_identical()
    if not live.get("ok"):
        print("FAILED:IMP-0002-probe1 live builds not identical")
        return 1

    measured = doc.get("measured_builds") or {}
    rec = str(measured.get("sha256") or "")
    campaign_self_consistent = bool(
        measured.get("equal") is True
        and measured.get("build1")
        and measured.get("build1") == measured.get("build2") == measured.get("build3")
        and measured.get("build3_independent_hasher") == measured.get("build1")
    )
    row = {
        "unit_id": UNIT,
        "probe": "probe1-determinism-rebuild",
        "determinism_live": True,
        "live_sha256": live["sha256"],
        "live_members": live.get("members"),
        "recorded_campaign_sha256": rec,
        "digest_equal_to_recorded_campaign": live["sha256"] == rec,
        "fixture_drift_note": (
            "create_pack_fixture was simplified after the recorded campaign; "
            "cross-time digest equality is not part of the unit contract - "
            "within-run equality plus recorded-campaign self-consistency is."
        ),
        "recorded_campaign_self_consistent": campaign_self_consistent,
    }
    print(json.dumps(row, indent=1))
    if not campaign_self_consistent:
        print("FAILED:IMP-0002-probe1 recorded campaign not internally consistent")
        return 1
    print(f"SUCCESS:{UNIT}-probe1 live determinism rebuild")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
