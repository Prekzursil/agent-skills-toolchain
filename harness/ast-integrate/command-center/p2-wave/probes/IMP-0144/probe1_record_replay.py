#!/usr/bin/env python3
"""Probe 1: record-then-replay yields a byte-identical plan and identical verdicts.

Evidence signals (catalog): (1) byte-equality of the replayed plan;
(2) zero spawns during replay, counted by the fake rail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / S.RECEIPT_REL


def main() -> int:
    run = S.record_and_replay()
    printable = {
        k: run[k]
        for k in (
            "dispatch_events",
            "event_count",
            "fail_verdicts",
            "plan_bytes",
            "plan_equal",
            "plan_sha256",
            "record_spawns",
            "replay_calls",
            "replay_spawns",
            "run_id",
            "slot_count",
            "slot_ids",
            "verdict_equal",
            "verdict_sha256",
            "verdicts",
        )
    }
    print(json.dumps(printable, sort_keys=True))
    if not run["pass"]:
        print("FAILED:IMP-0144-probe1 record-replay did not pass")
        return 1
    if run["replay_spawns"] != 0:
        print(f"FAILED:IMP-0144-probe1 replay spawns={run['replay_spawns']}")
        return 1
    if run["record_spawns"] < 1:
        print("FAILED:IMP-0144-probe1 record spawns vacuously zero")
        return 1
    if not ART.is_file():
        print("FAILED:IMP-0144-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0144-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0144" not in text:
        print("FAILED:IMP-0144-probe1 sentinel absent")
        return 1
    live_plan = run["plan_sha256"]
    art_plan = ((doc.get("report") or {}).get("plan_sha256")) or doc.get("plan_sha256")
    if art_plan != live_plan:
        print(f"FAILED:IMP-0144-probe1 receipt plan_sha256 {art_plan} != live {live_plan}")
        return 1
    print(
        f"plan_equal={run['plan_equal']} verdict_equal={run['verdict_equal']} "
        f"record_spawns={run['record_spawns']} replay_spawns={run['replay_spawns']}"
    )
    print("SUCCESS:IMP-0144-probe1 record-then-replay byte-identical plan and verdicts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
