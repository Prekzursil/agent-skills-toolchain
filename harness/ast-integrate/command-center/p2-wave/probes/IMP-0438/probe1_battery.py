#!/usr/bin/env python3
"""Named probe 1: live 16-mutation battery under the bare CI invocation.

Re-runs the canonical sixteen mutations with require_complete armed (the
default). Requires 16/16 caught, CONTROL exit 0, and the known-caught control
mutation M01 still red. Compares the live table to the receipt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import battery as B  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0438.json"
SENTINEL = "SENTINEL:IMP-0438:MUTATION-BATTERY-COMPLETE"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 128:
        print("FAILED:IMP-0438-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:IMP-0438-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0438-probe1 receipt self-declared", doc.get("state"))
        return 1

    live = B.run_battery(B.MUTATIONS, disarm=False)
    control = live["control"]
    rows = live["rows"]
    m01 = next(r for r in rows if r["id"] == "M01")
    survivors = live["survivor_ids"]

    recorded = {row["id"]: row for row in (doc.get("mutations") or []) if isinstance(row, dict)}
    drift = []
    for row in rows:
        rec = recorded.get(row["id"]) or {}
        post = rec.get("post_fix") or {}
        if post.get("caught") is not True:
            drift.append(f"{row['id']} receipt post_fix.caught != true")
        if row["caught"] is not True:
            drift.append(f"{row['id']} live not caught exit={row['exit_code']}")
        if row["caught"] and not row["claimed_check_in_output"] and row["id"] != "CONTROL":
            # Attribution: the claimed check must appear in CLI output.
            drift.append(f"{row['id']} caught but {row['claimed_check']} missing from output")

    ok = (
        live["caught"] == 16
        and live["n"] == 16
        and not survivors
        and control.get("exit_code") == 0
        and control.get("success_marker") is True
        and m01["caught"] is True
        and m01["claimed_check_in_output"] is True
        and not drift
    )
    summary = {
        "probe": "probe1-battery",
        "unit_id": "IMP-0438",
        "caught": live["caught"],
        "n": live["n"],
        "survivors": survivors,
        "control_exit": control.get("exit_code"),
        "m01_still_caught": m01["caught"],
        "drift": drift,
        "pass": ok,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"caught={live['caught']}/16 control_exit={control.get('exit_code')} "
        f"m01_caught={m01['caught']} survivors={survivors}"
    )
    if not ok:
        print("FAILED:IMP-0438-probe1 armed battery is not 16/16")
        return 1
    print("SUCCESS:IMP-0438-probe1 armed battery 16/16 and control mutation still caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
