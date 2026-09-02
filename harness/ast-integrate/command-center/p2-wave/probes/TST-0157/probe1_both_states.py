#!/usr/bin/env python3
"""Probe 1: both-states control for duplicate dispatch.

Contested: two sessions, one unit id -> exactly one EXECUTED, one
DUPLICATE-SUPPRESSED, one receipt. Control: two DIFFERENT ids dispatched
concurrently both EXECUTED with two receipts. Silence is a failure.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import work_claim as wc  # noqa: E402

UID = "TST-0157"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe1 {msg}")
    return 1


def main() -> int:
    repeats = 8
    contested_rows = []
    with tempfile.TemporaryDirectory(prefix="tst0157-p1-") as tmp:
        root = Path(tmp)
        for i in range(repeats):
            trial_root = root / f"contested-{i}"
            results = wc.concurrent_pair(
                trial_root,
                "UNIT-SAME",
                "UNIT-SAME",
                f"sess-a-{i}",
                f"sess-b-{i}",
                skew_a=0.0,
                skew_b=0.002 * (i % 3),
            )
            check = wc.contested_ok(results, trial_root, "UNIT-SAME")
            contested_rows.append(check)
            if not check["ok"]:
                return fail(f"contested trial {i} {check} results={results}")

        distinct_root = root / "distinct"
        distinct = wc.concurrent_pair(
            distinct_root,
            "UNIT-LEFT",
            "UNIT-RIGHT",
            "sess-left",
            "sess-right",
        )
        dcheck = wc.distinct_ok(distinct, distinct_root, "UNIT-LEFT", "UNIT-RIGHT")
        if not dcheck["ok"]:
            return fail(f"distinct-ids {dcheck} results={distinct}")

        # Serial second dispatch after a completed first must still suppress.
        serial_root = root / "serial"
        first = wc.dispatch(serial_root, "UNIT-SERIAL", "sess-1", payload="one")
        second = wc.dispatch(serial_root, "UNIT-SERIAL", "sess-2", payload="two")
        if first.get("status") != wc.EXECUTED:
            return fail(f"serial winner {first}")
        if second.get("status") != wc.DUPLICATE_SUPPRESSED:
            return fail(f"serial loser not typed: {second}")
        if wc.count_receipts(serial_root, "UNIT-SERIAL") != 1:
            return fail("serial wrote a second receipt")

    payload = {
        "probe": "probe1-both-states",
        "unit_id": UID,
        "pass": True,
        "contested_repeats": repeats,
        "contested_all_ok": all(r["ok"] for r in contested_rows),
        "distinct_ids_both_execute": dcheck["ok"],
        "serial_loser": second.get("status"),
        "silence_is_failure": True,
        "receipt_signal": "count of receipts/<id>.json",
        "status_signal": "both callers' returned status objects",
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    print(
        f"contested_ok={repeats}/{repeats} distinct_ok={dcheck['ok']} "
        f"serial_loser={second.get('status')}"
    )
    print(f"SUCCESS:{UID}-probe1 both-states: one winner + typed suppression; distinct ids both run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
