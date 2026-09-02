#!/usr/bin/env python3
"""Probe 1: both-states control (genuine must wake; cosmetic must not)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import watchlist as W  # noqa: E402

ART = REPO / "command-center/research/sources-frontier/RES-0180-watchlist-standing-recheck.json"
UNIT = "RES-0180"


def main() -> int:
    both = W.both_states()
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0180-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("unit_id") or "") != UNIT:
        print("FAILED:RES-0180-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:RES-0180" not in text:
        print("FAILED:RES-0180-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0180-probe1 self-declared", doc.get("state"))
        return 1
    if not both.get("pass"):
        print("FAILED:RES-0180-probe1 both-states")
        print(json.dumps(both.get("cases"), indent=1))
        return 1
    if not both.get("watcher_not_poller"):
        print("FAILED:RES-0180-probe1 watcher behaves as poller")
        return 1
    if not both.get("poller_wakes_on_both"):
        print("FAILED:RES-0180-probe1 poller control did not fire on cosmetic")
        return 1
    if not both.get("independent_regex_agrees"):
        print("FAILED:RES-0180-probe1 regex path disagrees with parser")
        return 1
    recorded = {c.get("id"): c for c in (doc.get("controls") or [])}
    for case in both["cases"]:
        rec = recorded.get(case["id"])
        if not rec:
            print("FAILED:RES-0180-probe1 missing control", case["id"])
            return 1
        if rec.get("watcher_wake") != case["watcher_wake"]:
            print("FAILED:RES-0180-probe1 drift", case["id"], rec, case)
            return 1
        if rec.get("verdict") != "PASS":
            print("FAILED:RES-0180-probe1 recorded verdict", case["id"], rec.get("verdict"))
            return 1
    mech = doc.get("mechanism") or {}
    if len(mech.get("signals_by_class") or []) < 4:
        print("FAILED:RES-0180-probe1 signals_by_class thin")
        return 1
    if len(mech.get("on_wake") or []) < 2:
        print("FAILED:RES-0180-probe1 on_wake missing")
        return 1
    out = {
        "probe": "probe1-both-states",
        "unit_id": UNIT,
        "pass": True,
        "watcher_not_poller": True,
        "cases": [(c["id"], c["verdict"]) for c in both["cases"]],
        "independent_regex_agrees": True,
    }
    print(json.dumps(out, indent=1, sort_keys=True))
    print("SUCCESS:RES-0180-probe1 both-states genuine wakes, cosmetic silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
