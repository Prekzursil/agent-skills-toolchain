#!/usr/bin/env python3
"""Probe 2 (independent reviewer): owner packet + both-states + leak detectors.

Starts from the catalog tests, not the author's summary:

1. Re-run the three scripted casts and require three distinct actions.
2. Owner-intervention packet: one foundation-level question, recommendation,
   stated default. Two questions and an already-settled id must fail.
3. Frozen clock / fixed pid must not move the production trace; leak flags must.
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
REQUIRED_RECEIPT = (
    "unit_id",
    "state",
    "sentinel",
    "question",
    "answer",
    "tests",
    "evidence",
    "reviewer",
    "artifacts",
    "three_way",
    "frozen_clock",
    "fixed_pid",
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0290-probe2 {msg}")
    return 1


def main() -> int:
    data = collect()
    flags = data["flags"]
    print(
        json.dumps(
            {
                "compound_rejected": flags["compound_rejected"],
                "distinct_actions": flags["distinct_actions"],
                "fixed_pid_unchanged": flags["fixed_pid_unchanged"],
                "frozen_clock_unchanged": flags["frozen_clock_unchanged"],
                "clock_leak_detector_fired": flags["clock_leak_detector_fired"],
                "owner_packet_ok": flags["owner_packet_ok"],
                "pid_leak_detector_fired": flags["pid_leak_detector_fired"],
                "settled_suppressed": flags["settled_suppressed"],
                "three_way_ok": flags["three_way_ok"],
                "two_question_rejected": flags["two_question_rejected"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not flags["three_way_ok"] or not flags["distinct_actions"]:
        return fail("reviewer re-run of three-way classification failed")
    if flags["generic_escalation"]:
        return fail("reviewer saw a single generic escalation")
    if not flags["frozen_clock_unchanged"]:
        return fail("frozen clock changed the production trace")
    if not flags["fixed_pid_unchanged"]:
        return fail("fixed PID changed the production trace")
    if not flags["clock_leak_detector_fired"]:
        return fail("clock-leak injection did not move the trace")
    if not flags["pid_leak_detector_fired"]:
        return fail("pid-leak injection did not move the trace")
    if data["pid_leak_injection"]["node_order_a"] == data["pid_leak_injection"]["node_order_b"]:
        return fail("pid leak hashes differed but node_order did not")
    if not flags["owner_packet_ok"]:
        return fail("legal owner packet was refused")
    packet = data["owner_packet"]
    if packet["check"]["question_count"] != 1:
        return fail("owner packet asked more than one question")
    if "recommendation" not in packet or "default" not in packet:
        return fail("owner packet missing recommendation or default")
    if not flags["two_question_rejected"]:
        return fail("two-question packet was accepted")
    if not flags["settled_suppressed"]:
        return fail("already-settled question was re-asked")
    if not flags["compound_rejected"]:
        return fail("compound question was accepted")

    garbage = {"totally": "unrelated", "passing_tests": 999999}
    missing = [k for k in REQUIRED_RECEIPT if k not in garbage]
    print(f"garbage_missing_contract_fields={len(missing)}")
    if len(missing) < 8:
        return fail("garbage looked like a TST-0290 receipt")

    if RECEIPT.is_file():
        text = RECEIPT.read_text(encoding="utf-8")
        doc = json.loads(text)
        if SENTINEL not in text:
            return fail("receipt sentinel absent")
        missing_doc = [k for k in REQUIRED_RECEIPT if k not in doc]
        if missing_doc:
            return fail(f"receipt missing {missing_doc}")
        if doc.get("frozen_clock", {}).get("trace_unchanged") is not True:
            return fail("receipt frozen_clock.trace_unchanged is not true")
        if doc.get("fixed_pid", {}).get("trace_unchanged") is not True:
            return fail("receipt fixed_pid.trace_unchanged is not true")
        sources = doc.get("nondeterminism_sources") or []
        if not any(s.get("source") == "wall-clock" for s in sources):
            return fail("receipt omitted wall-clock source")
        if not any(s.get("source") == "pid" for s in sources):
            return fail("receipt omitted pid source")
        leaked = [
            s
            for s in sources
            if s.get("source") in {"wall-clock", "pid"}
            and s.get("leaks_into_production_dag") is True
        ]
        if leaked:
            return fail("receipt claimed a production DAG leak live injection did not see")
        print("receipt_contract_ok=True")
    else:
        print("receipt_absent_on_this_run (library checks only)")

    print("SUCCESS:TST-0290-probe2 owner packet and both-states reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
