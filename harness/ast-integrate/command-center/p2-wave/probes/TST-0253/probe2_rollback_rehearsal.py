#!/usr/bin/env python3
"""Probe 2: rollback rehearsal postcondition probes (independent of probe 1).

Re-runs the live ROLLBACK-MANIFEST.md end to end in a scratch tree and
requires every step's postcondition to hold, including the corruption
observation and the byte-identical restore.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

RECEIPT = H.REPO / "command-center" / "receipts" / "TST-0253.json"
SENTINEL = "SUCCESS:TST-0253"
OUT = HERE / "probe2-rollback-rehearsal.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0253-probe2 {msg}")
    return 1


def receipt_ok(live: dict) -> bool | None:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        return None
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    answer = doc.get("answer_struct") or {}
    reb = answer.get("live_rollback_rehearsal") or {}
    n_steps = reb.get("n_steps")
    n_ok = reb.get("n_postconditions_ok")
    return (
        str(doc.get("state") or "").upper()
        not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
        and SENTINEL in text
        and reb.get("ok") is True
        and n_steps == live["n_steps"]
        and n_ok == live["n_postconditions_ok"]
    )


def main() -> int:
    rehearsal_root = HERE / "runtime" / "probe2-live-rollback"
    live = H.rehearse(H.LIVE_ROLLBACK, rehearsal_root)
    fixture = H.rehearse(
        "command-center/p2-wave/probes/TST-0253/fixtures/good-rollback.md",
        HERE / "runtime" / "probe2-fixture-rollback",
    )
    rec = receipt_ok(live)
    ids = [row["id"] for row in live.get("steps") or []]
    pc_ok = [row for row in live.get("steps") or [] if (row.get("postcondition") or {}).get("ok")]
    corrupt = None
    restore = None
    for row in live.get("steps") or []:
        if row.get("id") == "RB-2":
            corrupt = row
        if row.get("id") == "RB-3":
            restore = row
    payload = {
        "probe": "probe2-rollback-rehearsal",
        "unit_id": "TST-0253",
        "pass": bool(
            live.get("ok")
            and fixture.get("ok")
            and rec is not False
            and len(pc_ok) == live.get("n_steps")
        ),
        "live_ok": live.get("ok"),
        "fixture_ok": fixture.get("ok"),
        "n_steps": live.get("n_steps"),
        "n_postconditions_ok": live.get("n_postconditions_ok"),
        "step_ids": ids,
        "rb2_corrupt_observed": bool(
            ((corrupt or {}).get("postcondition") or {}).get("ok")
        ),
        "rb3_restore_match": bool(
            ((restore or {}).get("postcondition") or {}).get("reason") == "match"
        ),
        "rehearsal": live.get("rehearsal"),
        "receipt_present": RECEIPT.is_file(),
        "receipt_ok": rec,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not live.get("ok"):
        return fail(f"live rollback rehearsal {live.get('reason')}")
    if live.get("n_steps", 0) < 3:
        return fail(f"too few rollback steps: {live.get('n_steps')}")
    if live.get("n_postconditions_ok") != live.get("n_steps"):
        return fail("not every rollback step postcondition held")
    if not payload["rb2_corrupt_observed"]:
        return fail("RB-2 did not observe CORRUPTED-DEPLOY")
    if not payload["rb3_restore_match"]:
        return fail("RB-3 restore was not byte-identical to snapshot")
    if not fixture.get("ok"):
        return fail("fixture rollback rehearsal failed")
    if rec is False:
        return fail("receipt does not match live rollback rehearsal")
    print(
        f"live_steps={live['n_steps']} postconditions_ok={live['n_postconditions_ok']} "
        f"restore={payload['rb3_restore_match']}"
    )
    print("SUCCESS:TST-0253-probe2 rollback rehearsal postconditions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
