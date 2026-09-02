#!/usr/bin/env python3
"""Probe 2 (adversarial, from the tests): prefix-hash invariant + negative control.

Independent of the author's summary: take the prefix hash of the event log,
perform an owner intervention, and re-hash the same prefix. Then mutate a
prior event and assert the prefix-hash check FIRES. The rewrite API must
refuse. Reviewer starts here, not from the implementer's narrative.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.owner import (  # noqa: E402
    AppendOnlyError,
    PrefixTamperError,
    LiveCouncil,
    check_prefix,
    prefix_hash,
    run_negative_control,
)

UNIT = "IMP-0342"
ART = REPO / "command-center/receipts/IMP-0342.json"


def _check_receipt() -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "receipt missing"
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable {exc}"
    if not isinstance(doc, dict):
        return "receipt not object"
    if str(doc.get("unit_id")) != UNIT:
        return f"unit_id {doc.get('unit_id')}"
    if "SUCCESS:IMP-0342" not in text:
        return "sentinel absent"
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return f"self-declared {doc.get('state')}"
    owner_block = doc.get("owner_sign_off")
    if not isinstance(owner_block, dict):
        return "owner_sign_off block absent"
    if owner_block.get("reviewer_granted") is True:
        return "reviewer granted owner half (forbidden)"
    return None


def main() -> int:
    rec_err = _check_receipt()
    if rec_err:
        print(f"FAILED:IMP-0342-probe2 {rec_err}")
        return 1

    council = LiveCouncil("council-imp-0342-prefix", owner_id="owner-1")
    council.start(["alice", "bob"], seed="prefix")
    t1 = council.record_turn("alice", "position A")
    t2 = council.record_turn("bob", "position B")
    snap = council.snapshot_prefix()
    intact_before = check_prefix(
        council.log.events(), str(snap["prefix_hash"]), int(snap["n"])
    )
    council.pause("owner-1", "inject a constraint")
    council.inject_constraint("owner-1", "Do not rewrite position A or B.")
    council.resume("owner-1")
    intact_after = check_prefix(
        council.log.events(), str(snap["prefix_hash"]), int(snap["n"])
    )
    after_n = len(council.log)
    if after_n <= int(snap["n"]):
        print("FAILED:IMP-0342-probe2 intervention did not append")
        return 1
    full = prefix_hash(council.log.events())
    if full == snap["prefix_hash"]:
        print("FAILED:IMP-0342-probe2 full-log hash did not move after append")
        return 1
    live_a = next(e for e in council.log.events() if e["seq"] == t1["seq"])
    live_b = next(e for e in council.log.events() if e["seq"] == t2["seq"])
    if live_a["payload"]["text"] != "position A" or live_b["payload"]["text"] != "position B":
        print("FAILED:IMP-0342-probe2 prior texts changed")
        return 1
    print(
        json.dumps(
            {
                "intact_before": intact_before,
                "intact_after_intervention": intact_after,
                "prefix_n": snap["n"],
                "event_count_after": after_n,
                "full_hash_moved": full != snap["prefix_hash"],
            },
            sort_keys=True,
        )
    )
    if intact_before != "intact" or intact_after != "intact":
        print("FAILED:IMP-0342-probe2 prefix hash changed across intervention")
        return 1

    nc = run_negative_control()
    print(json.dumps({"negative_control": nc}, sort_keys=True))
    if not nc["prefix_check_fired"]:
        print("FAILED:IMP-0342-probe2 prefix check did not FIRE on mutation")
        return 1
    if not nc["rewrite_api_refused"]:
        print("FAILED:IMP-0342-probe2 rewrite API did not refuse")
        return 1
    if not nc["intact_on_clean_log"]:
        print("FAILED:IMP-0342-probe2 clean log prefix check was not intact")
        return 1

    bad = LiveCouncil("council-imp-0342-both", owner_id="owner-1")
    bad.start(["alice"], seed="both")
    turn = bad.record_turn("alice", "keep me")
    snap2 = bad.snapshot_prefix()
    silent = check_prefix(
        bad.log.events(), str(snap2["prefix_hash"]), int(snap2["n"])
    )
    bad.log.debug_overwrite_payload(int(turn["seq"]), {"text": "mutated"})
    fired = False
    try:
        check_prefix(
            bad.log.events(), str(snap2["prefix_hash"]), int(snap2["n"])
        )
    except PrefixTamperError:
        fired = True
    print(f"both_states silent_on_good={silent == 'intact'} fired_on_bad={fired}")
    if silent != "intact" or not fired:
        print("FAILED:IMP-0342-probe2 both-states prefix check")
        return 1

    try:
        bad.log.truncate()
        print("FAILED:IMP-0342-probe2 truncate did not refuse")
        return 1
    except AppendOnlyError:
        print("truncate_refused=True")

    print("SUCCESS:IMP-0342-probe2 prefix-hash invariant and mutation FIRE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
