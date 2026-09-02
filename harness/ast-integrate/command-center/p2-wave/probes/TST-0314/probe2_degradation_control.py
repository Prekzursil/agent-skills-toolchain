#!/usr/bin/env python3
"""Probe 2: post-KEEP regression alarm + permissive-gate KEEP-rate jump.

Catalog tests:
  * Post-KEEP regression rate: how often a KEEP is later reverted; a
    rising rate is the key alarm.
  * Degradation control: inject a deliberately permissive gate and
    confirm the meta-benchmark detects the KEEP-rate jump.

The statistics reviewer re-runs the KEEP-rate comparison from the raw
per-case results and independently reproduces Cohen's h and the
Newcombe interval.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

UNIT = "TST-0314"


def main() -> int:
    report = H.degradation_control_checks()
    slim = {
        "ok": report.get("ok"),
        "checks": report.get("checks"),
        "prereg": report.get("prereg"),
        "jump_point": (report.get("jump") or {}).get("jump"),
        "cohens_h": (report.get("jump") or {}).get("cohens_h"),
        "interval": (report.get("jump") or {}).get("interval"),
        "degrading_fired": (report.get("degrading_alarm") or {}).get("fired"),
        "stable_fired": (report.get("stable_alarm") or {}).get("fired"),
    }
    print(json.dumps(slim, sort_keys=True, default=str))
    if not report.get("ok"):
        print(f"FAILED:{UNIT}-probe2 degradation-control")
        print(json.dumps(report.get("checks"), indent=2)[:3000])
        return 1
    jump = report["jump"]
    deg = report["degrading_alarm"]
    print(
        f"post_keep_stable_silent={report['checks']['stable_post_keep_silent']} "
        f"post_keep_degrading_fires={deg['fired']} delta={deg['delta']:.4f} "
        f"permissive_jump={jump['jump']:.4f} h={jump['cohens_h']:.4f} "
        f"ci=({jump['interval']['low']:.4f},{jump['interval']['high']:.4f})"
    )
    print(
        f"SUCCESS:{UNIT}-probe2 post-KEEP regression alarm + permissive "
        "KEEP-rate jump detected; reviewer reproduced h and interval"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
