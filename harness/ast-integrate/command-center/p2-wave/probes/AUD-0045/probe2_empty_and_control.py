#!/usr/bin/env python3
"""Probe 2: re-execute empty and known-bad inputs; require both-states controls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

ART = REPO / "command-center/audit/AUD-0045-fail-open-gate-census.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:AUD-0045-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:AUD-0045-probe2 self-declared", doc.get("state"))
        return 1

    live_rows = [C.compact_exec_row(r) for r in C.execute_gates()]
    live_by = {r["id"]: r for r in live_rows}
    rec_by = {r["id"]: r for r in (doc.get("executed_gates") or [])}

    if set(live_by) != set(rec_by):
        print("FAILED:AUD-0045-probe2 gate id set drift", set(live_by) ^ set(rec_by))
        return 1

    drift = []
    for gid, live in live_by.items():
        rec = rec_by[gid]
        if live["class"] != rec["class"]:
            drift.append(f"{gid} class live={live['class']} rec={rec['class']}")
        if live["empty"]["exit_code"] != rec["empty"]["exit_code"]:
            drift.append(f"{gid} empty-exit drift")
        if live["known_bad"]["exit_code"] != rec["known_bad"]["exit_code"]:
            drift.append(f"{gid} known-bad-exit drift")
    if drift:
        print("FAILED:AUD-0045-probe2", drift)
        return 1

    silent = live_by["control-silent-always"]
    closed = live_by["control-closed-always"]
    if silent["class"] != "measures-nothing":
        print("FAILED:AUD-0045-probe2 silent control not measures-nothing", silent)
        return 1
    if closed["class"] != "fail-closed":
        print("FAILED:AUD-0045-probe2 closed control not fail-closed", closed)
        return 1

    m16 = live_by["cc-validate-m16-disarmed-surface"]
    if m16["empty"]["exit_code"] != 0 or m16["known_bad"]["exit_code"] == 0:
        print("FAILED:AUD-0045-probe2 M16 both-states", m16)
        return 1

    freeze_none = live_by["freeze-gate-clean-plus-checks-none"]
    if freeze_none["empty"]["exit_code"] != 0 or freeze_none["known_bad"]["exit_code"] == 0:
        print("FAILED:AUD-0045-probe2 freeze CLEAN+NONE both-states", freeze_none)
        return 1

    freeze_off = live_by["freeze-gate-not-frozen"]
    if freeze_off["class"] != "measures-nothing":
        print("FAILED:AUD-0045-probe2 freeze-not-frozen should measure nothing")
        return 1

    rec_fail = list(doc.get("fail_open_ids") or [])
    live_fail = [
        r["id"]
        for r in live_rows
        if r["class"] in {"fail-open-empty", "measures-nothing"}
    ]
    if rec_fail != live_fail:
        print("FAILED:AUD-0045-probe2 fail_open_ids drift", rec_fail, live_fail)
        return 1

    summary = {
        "probe": "probe2-empty-and-control",
        "n": len(live_rows),
        "fail_open_ids": live_fail,
        "control_silent": silent["class"],
        "control_closed": closed["class"],
        "m16_disarmed_exit": m16["empty"]["exit_code"],
        "m16_armed_exit": m16["known_bad"]["exit_code"],
        "freeze_none_empty_exit": freeze_none["empty"]["exit_code"],
        "freeze_none_bad_exit": freeze_none["known_bad"]["exit_code"],
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"n={len(live_rows)} fail_open={live_fail} "
        f"m16={m16['empty']['exit_code']}/{m16['known_bad']['exit_code']} "
        f"freeze_none={freeze_none['empty']['exit_code']}/{freeze_none['known_bad']['exit_code']}"
    )
    print("SUCCESS:AUD-0045-probe2 empty-input execution and known-bad controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
