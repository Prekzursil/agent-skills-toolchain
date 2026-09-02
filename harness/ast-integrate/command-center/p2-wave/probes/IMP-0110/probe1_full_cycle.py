#!/usr/bin/env python3
"""Named probe 1: report → dispute-window → dispute → resolve event sequence.

Signal 1 of the catalog evidence requirement. Also confirms a resolved report
retains both the original report body and the publisher dispute text.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.event_log import EventLog  # noqa: E402
from marketplace.moderation import (  # noqa: E402
    DISPUTE_BODY_FIXTURE,
    FULL_CYCLE_EVENT_TYPES,
    REPORT_BODY_FIXTURE,
    ModerationQueue,
    run_full_cycle,
)

RECEIPT = REPO / "command-center/receipts/IMP-0110.json"
SENTINEL = "SUCCESS:IMP-0110"


def _check_receipt() -> None:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        raise SystemExit("FAILED:IMP-0110-probe1 receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        raise SystemExit("FAILED:IMP-0110-probe1 sentinel absent")
    doc = json.loads(text)
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:IMP-0110-probe1 self-declared:{state}")


def main() -> int:
    _check_receipt()
    with tempfile.TemporaryDirectory(prefix="imp0110-p1-") as tmp:
        log = EventLog(Path(tmp) / "events.jsonl")
        q = ModerationQueue(log)
        result = run_full_cycle(q)
        types = q.cycle_event_types(result["report_id"])
        if types != list(FULL_CYCLE_EVENT_TYPES):
            print("FAILED:IMP-0110-probe1 event sequence", types)
            return 1
        if result["report"]["body"] != REPORT_BODY_FIXTURE:
            print("FAILED:IMP-0110-probe1 report body not retained")
            return 1
        if result["dispute"]["body"] != DISPUTE_BODY_FIXTURE:
            print("FAILED:IMP-0110-probe1 dispute body not retained")
            return 1
        if result["state"] != "resolved" or result["resolution"] is None:
            print("FAILED:IMP-0110-probe1 not resolved")
            return 1
        log.verify_chain()
        payload = {
            "pass": True,
            "probe": "probe1-full-cycle",
            "unit_id": "IMP-0110",
            "event_types": types,
            "report_retained": True,
            "dispute_retained": True,
            "chain_ok": True,
            "report_id": result["report_id"],
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            "event_sequence="
            + ",".join(types)
            + " report_retained=True dispute_retained=True"
        )
        print("SUCCESS:IMP-0110-probe1 full-cycle event sequence")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
