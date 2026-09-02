#!/usr/bin/env python3
"""Probe 1: live coverage table + both-states detector control.

Coverage: every step in RUNBOOK.md and ROLLBACK-MANIFEST.md is classified.
PASS of the live target requires zero PROSE_ONLY steps. Both-states: a
good fixture's postconditions pass while a deliberately broken step fails.
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
OUT = HERE / "probe1-coverage-and-both-states.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0253-probe1 {msg}")
    return 1


def receipt_ok(live: dict) -> bool | None:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        return None
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    answer = doc.get("answer_struct") or {}
    n_live = answer.get("n_live_steps")
    n_prose = answer.get("n_prose_only")
    return (
        str(doc.get("state") or "").upper()
        not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
        and SENTINEL in text
        and n_live == live["n_live_steps"]
        and n_prose == live["n_prose_only"]
        and answer.get("both_states_ok") is True
        and live["both_states"]["ok"] is True
    )


def main() -> int:
    live = H.measure()
    states = live["both_states"]
    runbook = live["runbook"]
    rollback = live["rollback_coverage"]
    rec = receipt_ok(live)
    payload = {
        "probe": "probe1-coverage-and-both-states",
        "unit_id": "TST-0253",
        "pass": bool(
            live["target_pass"]
            and states["ok"]
            and runbook["ok"]
            and rollback["ok"]
            and rec is not False
        ),
        "n_live_steps": live["n_live_steps"],
        "n_prose_only": live["n_prose_only"],
        "runbook_ok": runbook["ok"],
        "rollback_coverage_ok": rollback["ok"],
        "both_states": {
            "ok": states["ok"],
            "good_passes": states["good_passes"],
            "broken_fails": states["broken_fails"],
            "broken_ids": states["broken_ids"],
            "prose_only_count": states["prose_only_count"],
            "naive_would_pass_prose": states["naive_would_pass_prose"],
        },
        "coverage_ids": [row["id"] for row in live["coverage_table"]],
        "receipt_present": RECEIPT.is_file(),
        "receipt_ok": rec,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not runbook["present"]:
        return fail("RUNBOOK.md absent")
    if not rollback["present"]:
        return fail("ROLLBACK-MANIFEST.md absent")
    if runbook["n_steps"] < 1 or rollback["n_steps"] < 1:
        return fail("zero steps in a live document")
    if live["n_prose_only"] != 0:
        return fail(f"prose-only steps: {runbook['prose_ids']+rollback['prose_ids']}")
    if not runbook["ok"]:
        return fail(f"runbook coverage {runbook['reason']}")
    if not rollback["ok"]:
        return fail(f"rollback coverage {rollback['reason']}")
    if not states["good_passes"]:
        return fail("good fixture postconditions did not pass")
    if not states["broken_fails"]:
        return fail("broken step postcondition did not fail")
    if states["prose_only_count"] != 1:
        return fail("prose-only fixture was not classified PROSE_ONLY")
    if not states["naive_would_pass_prose"]:
        return fail("naive Success-string detector did not fire on prose fixture")
    if not states["ok"]:
        return fail("both-states control failed")
    if rec is False:
        return fail("receipt does not match live coverage")
    print(
        f"live_steps={live['n_live_steps']} prose_only={live['n_prose_only']} "
        f"broken_fails={states['broken_fails']}"
    )
    print("SUCCESS:TST-0253-probe1 coverage table + both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
