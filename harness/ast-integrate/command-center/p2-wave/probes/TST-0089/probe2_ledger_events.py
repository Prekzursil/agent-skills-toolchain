#!/usr/bin/env python3
"""Named probe 2: ledger types distinguish monitor death from work death.

Negative control: a heartbeat+result silence view is identical in both
scenarios at the post-kill snapshot, which is why mtime/silence is banned.
"""
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
    silence_view,
    test_ledger_distinguishes_monitor_death_from_work_death,
    typed_view,
)

ART = REPO / "command-center/receipts/TST-0089.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def check_receipt() -> dict:
    if not ART.is_file() or ART.stat().st_size < 200:
        raise SystemExit("FAILED:TST-0089-probe2 receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0089" not in text:
        raise SystemExit("FAILED:TST-0089-probe2 sentinel absent")
    state = str(doc.get("state") or "").upper()
    if state in NOT_DELIVERING:
        raise SystemExit(f"FAILED:TST-0089-probe2 self-declared:{state}")
    return doc


def main() -> int:
    check_receipt()
    with tempfile.TemporaryDirectory(prefix="tst0089-p2-") as tmp:
        root = Path(tmp)
        kill_mon = run_scenario("kill-monitor", root / "kill-monitor")
        kill_work = run_scenario("kill-work", root / "kill-work")
        test_ledger_distinguishes_monitor_death_from_work_death(kill_mon, kill_work)
    sa = silence_view(kill_mon["silence_snapshot"])
    sb = silence_view(kill_work["silence_snapshot"])
    summary = {
        "probe": "probe2-ledger-events",
        "unit_id": "TST-0089",
        "pass": True,
        "kill_monitor_typed": typed_view(kill_mon["event_types"]),
        "kill_work_typed": typed_view(kill_work["event_types"]),
        "silence_views_collide": sa == sb,
        "silence_view": sa,
        "kill_monitor_has_work_completed": "work-completed" in kill_mon["event_types"],
        "kill_work_has_work_died": "work-died" in kill_work["event_types"],
        "mtime_not_used": True,
    }
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    print(
        f"typed kill-monitor={summary['kill_monitor_typed']} "
        f"kill-work={summary['kill_work_typed']} silence_collide={sa == sb}"
    )
    print("SUCCESS:TST-0089-probe2 ledger distinguishes monitor-died from work-died")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
