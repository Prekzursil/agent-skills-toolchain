#!/usr/bin/env python3
"""Probe 1: four-state confusion matrix against the orchestrator monitor."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
from common import FOUR_TRUTHS, OUT_REL, REPO, SENTINEL, TRUTH_S1, UNIT_ID  # noqa: E402

ART = REPO / OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT_ID}-probe1 {msg}")
    return 1


def main() -> int:
    live = E.run_matrix()
    printable = {
        "probe": "probe1-four-state-matrix",
        "unit_id": UNIT_ID,
        "pass": live["pass"],
        "confusion_matrix": live["confusion_matrix"],
        "four_distinct": live["four_distinct"],
        "plainly_running_ok": live["plainly_running_ok"],
        "finished_versus_stalled_distinct": live["finished_versus_stalled_distinct"],
        "live_work_not_false_dead": live["live_work_not_false_dead"],
        "reported": [r["reported"] for r in live["rows"]],
        "truths": list(FOUR_TRUTHS),
    }
    print(json.dumps(printable, sort_keys=True))
    if not live["four_distinct"]:
        return fail(f"not four distinct labels {printable['reported']}")
    if not live["plainly_running_ok"]:
        return fail("plainly-running control missed")
    if not live["finished_versus_stalled_distinct"]:
        return fail("finished vs stalled not distinct")
    if not live["live_work_not_false_dead"]:
        return fail("live work with dead monitor not RUNNING_MONITOR_DEAD")
    if not live["pass"]:
        return fail("matrix did not pass")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("catalog sentinel absent")
    art_cm = doc.get("confusion_matrix") or {}
    if art_cm.get(TRUTH_S1) != live["confusion_matrix"].get(TRUTH_S1):
        return fail("artifact S1 drifted from live matrix")
    if sorted(art_cm.values()) != sorted(live["confusion_matrix"].values()):
        return fail(
            f"artifact matrix {art_cm} != live {live['confusion_matrix']}"
        )
    if not doc.get("four_distinct"):
        return fail("artifact four_distinct is not true")
    print(
        "SUCCESS:ADV-0124-probe1 four-state matrix "
        f"{live['confusion_matrix']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
