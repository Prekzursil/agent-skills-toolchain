#!/usr/bin/env python3
"""Named probe 1: remote work survives SIGKILL of the monitor and is harvestable."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from runtime import (  # noqa: E402
    run_scenario,
    test_results_are_harvestable_after_monitor_death,
    test_work_survives_monitor_death,
)

ART = REPO / "command-center/receipts/TST-0089.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def check_receipt() -> dict:
    if not ART.is_file() or ART.stat().st_size < 200:
        raise SystemExit("FAILED:TST-0089-probe1 receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0089" not in text:
        raise SystemExit("FAILED:TST-0089-probe1 sentinel absent")
    state = str(doc.get("state") or "").upper()
    if state in NOT_DELIVERING:
        raise SystemExit(f"FAILED:TST-0089-probe1 self-declared:{state}")
    if doc.get("unit_id") != "TST-0089" and doc.get("id") != "TST-0089":
        raise SystemExit("FAILED:TST-0089-probe1 unit_id")
    return doc


def main() -> int:
    check_receipt()
    with tempfile.TemporaryDirectory(prefix="tst0089-p1-") as tmp:
        result = run_scenario("kill-monitor", Path(tmp) / "run")
        test_work_survives_monitor_death(result)
        test_results_are_harvestable_after_monitor_death(result)
    summary = {
        "probe": "probe1-work-survives-harvest",
        "unit_id": "TST-0089",
        "pass": True,
        "work_alive_after_monitor_kill": result["work_alive_after_monitor_kill"],
        "work_exit": result["work_exit"],
        "harvest_ok": result["harvest"]["ok"],
        "harvest_nonce_matches": result["harvest"]["nonce"] == result["nonce"],
        "ledger_events": [
            t
            for t in result["event_types"]
            if t in {"monitor-died", "work-completed", "work-died", "harvest-recovered"}
        ],
    }
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    print(
        "work_alive_after_kill="
        f"{result['work_alive_after_monitor_kill']} exit={result['work_exit']} "
        f"harvest_ok={result['harvest']['ok']}"
    )
    print("SUCCESS:TST-0089-probe1 work survives monitor death and harvest recovers result")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
