#!/usr/bin/env python3
"""Probe 1: join cited greens to SHA-addressed attempt ledgers.

Reports attempt distribution, not pass rate. Both-states: join fires on a
laundered green (cited only the last pass) and is silent on an honest
single-attempt green. Naive pass-rate scoring misses the laundering.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ledger as L  # noqa: E402

ART = L.REPO / "command-center/adversarial/ADV-0090-rerun-until-green-laundering.json"


def main() -> int:
    report = L.probe1_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    dist = report["distribution"]
    both = report["both_states"]
    live = report["live_receipts"]
    print(
        f"joinable={dist['n_joinable']} unjoinable={dist['n_unjoinable']} "
        f"multi={dist['n_multi_attempt']} laundered={dist['n_laundered']} "
        f"hist={dist['histogram']}"
    )
    print(
        f"both_states fire_laundered={both['join_fires_on_laundered']} "
        f"silent_honest={both['join_silent_on_honest_single']} "
        f"naive_misses={both['naive_pass_rate_misses_laundering']}"
    )
    print(
        f"live_receipts scanned={live['scanned']} success={live['success_n']} "
        f"joinable={live['joinable_n']} unjoinable={live['unjoinable_n']}"
    )
    if not report["pass"]:
        print("FAILED:ADV-0090-probe1 join/both-states")
        return 1
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:ADV-0090" not in text:
            print("FAILED:ADV-0090-probe1 artifact sentinel absent")
            return 1
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            print(f"FAILED:ADV-0090-probe1 self-declared {doc.get('state')}")
            return 1
    print(
        "SUCCESS:ADV-0090-probe1 SHA-join reports attempt distribution; "
        "laundering detected; naive pass-rate misses it"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
