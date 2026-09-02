#!/usr/bin/env python3
"""Probe 2: harvest after monitor death; idle-alive is not dead.

Mechanically different from probe 1: durable-ledger harvest plus the
DETECTOR CONTROL re-run on the known-broken mtime-only fixture.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0047-monitor-liveness.json"


def main() -> int:
    harvest = S.harvest_after_monitor_death()
    idle = S.idle_alive()
    printable = {
        "harvest_pass": harvest["pass"],
        "monitor_killed": harvest["monitor_killed"],
        "remote_continued": harvest["remote_continued"],
        "terminal_in_durable_ledger": harvest["terminal_in_durable_ledger"],
        "harvested": harvest["harvested"],
        "harvest_verdict": (harvest.get("harvest_verdict") or {}).get("verdict"),
        "idle_pass": idle["pass"],
        "idle_verdict": idle["monitor"]["verdict"],
        "idle_bytes_unchanged": idle["artifact_bytes_unchanged"],
        "idle_reported_dead": idle["reported_dead"],
        "idle_mtime_only": idle["mtime_only"]["verdict"],
        "detector_control_mtime_calls_idle_stalled": idle["mtime_only"]["verdict"]
        == "STALLED",
    }
    print(json.dumps(printable, sort_keys=True))
    if not harvest["pass"]:
        print("FAILED:CNF-0047-probe2 harvest lost after monitor death")
        return 1
    if not idle["pass"]:
        print("FAILED:CNF-0047-probe2 idle-alive reported dead")
        return 1
    if not ART.is_file():
        print("FAILED:CNF-0047-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0047-probe2 self-declared {doc.get('state')}")
        return 1
    h = doc.get("harvest_after_monitor_death") or {}
    if not (h.get("monitor_killed") and h.get("remote_continued") and h.get("harvested")):
        print("FAILED:CNF-0047-probe2 artifact harvest flags false")
        return 1
    idle_doc = doc.get("idle_alive") or {}
    if idle_doc.get("reported_dead") is not False:
        print("FAILED:CNF-0047-probe2 artifact idle reported dead")
        return 1
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("detector_control_rerun") is not True:
        print("FAILED:CNF-0047-probe2 detector control not re-run")
        return 1
    print(
        "SUCCESS:CNF-0047-probe2 harvest-after-death "
        f"idle={printable['idle_verdict']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
