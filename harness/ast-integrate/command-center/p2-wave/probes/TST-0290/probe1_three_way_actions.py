#!/usr/bin/env python3
"""Probe 1: three-way classification on three scripted runs, distinct actions.

Catalog evidence: a single generic escalation for all three is the failure
this unit exists to catch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from measure import REPO, collect  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "TST-0290.json"
SENTINEL = "SUCCESS:TST-0290"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0290-probe1 {msg}")
    return 1


def main() -> int:
    data = collect()
    policy = data["policy"]
    flags = data["flags"]
    print(
        json.dumps(
            {
                "actions": policy["actions"],
                "deadlock_proposition_id": policy["deadlock_proposition_id"],
                "distinct_actions": policy["distinct_actions"],
                "generic_escalation": policy["generic_escalation"],
                "kinds": policy["kinds"],
                "rows": policy["rows"],
                "run_a_sha256": data["run_a"]["trace_hash"],
                "run_b_sha256": data["run_b"]["trace_hash"],
                "same_seed_identical": flags["same_seed_identical"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not policy["ok"]:
        return fail(f"three-way mismatches={policy['mismatches']}")
    if policy["generic_escalation"]:
        return fail("all three casts took the same action")
    if not policy["distinct_actions"]:
        return fail(f"actions not distinct: {policy['actions']}")
    if not policy["productive_dissent_preserved"]:
        return fail("productive disagreement escalated or lost dissent")
    if not policy["stalled_operational"]:
        return fail("stalled runtime treated as a deliberation outcome")
    if policy["deadlock_proposition_id"] != "P-CUTOVER":
        return fail("deadlock escalation did not name P-CUTOVER")
    if not flags["same_seed_identical"]:
        return fail("same seed produced different trace hashes")
    if not flags["different_seed_diverges"]:
        return fail("different seed did not change the trace")

    by_name = {row["name"]: row for row in policy["rows"]}
    if by_name["productive"]["escalated"] is not False:
        return fail("productive disagreement escalated")
    if by_name["deadlock"]["escalated"] is not True:
        return fail("genuine deadlock did not escalate")
    if by_name["stalled"]["escalated"] is not False:
        return fail("stalled runtime escalated as deadlock")
    if by_name["stalled"]["kind"] == by_name["deadlock"]["kind"]:
        return fail("stall and deadlock collapsed to one kind")

    if RECEIPT.is_file():
        text = RECEIPT.read_text(encoding="utf-8")
        doc = json.loads(text)
        if SENTINEL not in text:
            return fail("receipt sentinel absent")
        cmp_ = doc.get("trace_hash_comparison") or {}
        if cmp_.get("run_a_sha256") != data["run_a"]["trace_hash"]:
            return fail("receipt run_a_sha256 is not the live hash")
        if cmp_.get("identical") is not True:
            return fail("receipt did not record identical same-seed traces")
        three = (doc.get("three_way") or {}).get("rows") or []
        live = {row["name"]: row["action"] for row in policy["rows"]}
        recorded = {row.get("name"): row.get("action") for row in three}
        if recorded and recorded != live:
            return fail(f"receipt three-way table drifted from live {recorded}")
        print("receipt_matches_live_three_way=True")
    else:
        print("receipt_absent_on_this_run (library checks only)")

    print("SUCCESS:TST-0290-probe1 three-way classification distinct actions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
