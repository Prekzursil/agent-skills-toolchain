#!/usr/bin/env python3
"""Probe 1: live rollback rehearsal on a disposable profile.

Mechanically: execute additive-restore, then compute the set difference of
available commands and user-data paths (before minus after). The difference
must be empty and the planted user-data file must survive byte-identical.

A rehearsal that was never executed is NOT-CHECKED, not passing.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import PLANTED_REL, rehearse  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0474.json"
SENTINEL = "SENTINEL:IMP-0474:ROLLBACK-NON-DESTRUCTIVE"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0474-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0474-probe1 unparseable:{type(exc).__name__}")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0474-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:IMP-0474-probe1 sentinel-absent")
        return 1
    recorded = doc.get("rollback_rehearsal") or {}
    if recorded.get("rehearsal_executed") is not True:
        print("FAILED:IMP-0474-probe1 rehearsal-never-executed")
        return 1
    if recorded.get("verdict") == "NOT-CHECKED":
        print("FAILED:IMP-0474-probe1 rehearsal recorded as NOT-CHECKED")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0474-p1-") as tmp:
        result = rehearse(Path(tmp), mode="additive")

    report = result["rollback"]
    diff = report.get("set_difference") or {}
    planted = result["planted"]
    restored = result["managed_restored"]

    live = {
        "probe": "probe1-rehearsal",
        "unit_id": "IMP-0474",
        "rehearsal_executed": result.get("rehearsal_executed") is True,
        "mode": "additive",
        "command_diff": diff.get("commands_present_before_absent_after"),
        "user_data_diff": diff.get("user_data_present_before_absent_after"),
        "set_difference_empty": diff.get("empty"),
        "planted_rel": PLANTED_REL,
        "planted_survived": planted.get("survived"),
        "planted_byte_identical": planted.get("byte_identical"),
        "managed_restored": restored.get("ok"),
        "preservation_holds": result.get("preservation_holds"),
        "commands_before": (report.get("before") or {}).get("command_paths"),
        "commands_after": (report.get("after") or {}).get("command_paths"),
        "user_data_before": (report.get("before") or {}).get("user_data_paths"),
        "user_data_after": (report.get("after") or {}).get("user_data_paths"),
        "pass": False,
    }

    if not live["rehearsal_executed"]:
        print("FAILED:IMP-0474-probe1 live rehearsal not executed")
        print(json.dumps(live, indent=2, default=str)[:3000])
        return 1
    if live["set_difference_empty"] is not True:
        print("FAILED:IMP-0474-probe1 set-difference not empty")
        print(json.dumps(live, indent=2, default=str)[:4000])
        return 1
    if not live["planted_survived"]:
        print("FAILED:IMP-0474-probe1 planted user-data did not survive")
        print(json.dumps(live, indent=2, default=str)[:3000])
        return 1
    if not live["managed_restored"]:
        print("FAILED:IMP-0474-probe1 managed N-1 files not restored")
        print(json.dumps(live, indent=2, default=str)[:3000])
        return 1
    if not live["preservation_holds"]:
        print("FAILED:IMP-0474-probe1 preservation_holds false")
        return 1

    rec_diff = recorded.get("set_difference") or {}
    if rec_diff.get("empty") is not True:
        print("FAILED:IMP-0474-probe1 artifact set-difference not empty")
        return 1
    if recorded.get("planted_survived") is not True:
        print("FAILED:IMP-0474-probe1 artifact planted_survived not true")
        return 1

    live["pass"] = True
    print(json.dumps(live, sort_keys=True))
    print(
        "rehearsal_executed=True set_difference_empty=True "
        f"planted_survived=True managed_restored=True "
        f"commands_before={len(live['commands_before'] or [])} "
        f"user_data_before={len(live['user_data_before'] or [])}"
    )
    print("SUCCESS:IMP-0474-probe1 additive rollback rehearsal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
