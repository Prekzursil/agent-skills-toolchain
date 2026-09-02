#!/usr/bin/env python3
"""Probe 1: both-states — threshold+1 fires; threshold-1 is silent.

Re-runs the trigger against isolated queues and checks the catalog receipt
still contains the pasted enqueue unit ids (two signals).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONF = REPO / "command-center" / "confirmation"
sys.path.insert(0, str(CONF))

from expansion_proof import both_states  # noqa: E402
from class_expansion import trigger_source_anchor  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0139.json"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0139-p1-") as tmp:
        result = both_states(REPO, Path(tmp))
        fire = result["fire"]
        silent = result["silent"]
        persisted = json.loads(Path(fire["queue_path"]).read_text(encoding="utf-8"))
        disk_ids = [e["unit_id"] for e in persisted.get("entries") or []]
    print(json.dumps({
        "probe": "probe1-both-states",
        "pass": result["pass"],
        "fire_decision": fire["decision"],
        "fire_rate": fire["rate"],
        "fire_delta": fire["queue_length_delta"],
        "created_n": len(fire["created_unit_ids"]),
        "first_unit_id": (fire["created_unit_ids"] or [None])[0],
        "silent_decision": silent["decision"],
        "silent_delta": silent["queue_length_delta"],
        "disk_n": len(disk_ids),
    }, sort_keys=True))
    if not result["pass"]:
        print("FAILED:CNF-0139-probe1 both-states")
        return 1
    if fire["decision"] != "EXPAND" or silent["decision"] != "SILENT":
        print("FAILED:CNF-0139-probe1 decisions")
        return 1
    if len(fire["created_unit_ids"]) != 20:
        print("FAILED:CNF-0139-probe1 entire class not enqueued")
        return 1
    if fire["queue_length_delta"] != 20 or silent["queue_length_delta"] != 0:
        print("FAILED:CNF-0139-probe1 length delta")
        return 1
    if disk_ids != fire["created_unit_ids"]:
        print("FAILED:CNF-0139-probe1 persisted entries != created_unit_ids")
        return 1

    if not ART.is_file():
        print("FAILED:CNF-0139-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0139-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNF-0139" not in text:
        print("FAILED:CNF-0139-probe1 sentinel absent")
        return 1
    cited = ((doc.get("trigger") or {}).get("source") or {}).get("citation") or ""
    live_anchor = trigger_source_anchor()["citation"]
    if cited != live_anchor:
        print(f"FAILED:CNF-0139-probe1 trigger citation drift {cited!r} vs {live_anchor!r}")
        return 1
    receipt_ids = ((doc.get("evidence") or {}).get("created_unit_ids")) or []
    if "CNF-0139-REV-synth-bad-plus-one-m01" not in receipt_ids:
        print("FAILED:CNF-0139-probe1 receipt missing created unit id")
        return 1
    if len(receipt_ids) != 20:
        print("FAILED:CNF-0139-probe1 receipt unit id count")
        return 1
    two = (doc.get("evidence") or {}).get("two_signals") or {}
    if int(two.get("queue_length_delta") or 0) != 20:
        print("FAILED:CNF-0139-probe1 receipt length delta")
        return 1
    if len(two.get("persisted_unit_ids_on_disk") or []) != 20:
        print("FAILED:CNF-0139-probe1 receipt persisted ids")
        return 1
    print("SUCCESS:CNF-0139-probe1 both-states fire and silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
