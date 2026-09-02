#!/usr/bin/env python3
"""Probe 1: reproduce the estate-local blocking case as an executable procedure.

Both-states: A7-full denies unsigned unapproved Write of this unit's receipt
and denies catalog MENTION of a canary secret; the surviving minimum allows
both. P0 unsigned-plugin / canary-bundle / untrusted-USE stay denied.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A7/REFUTATION.json"


def main() -> int:
    run = S.run_scenario()
    printable = {k: run[k] for k in sorted(run) if k != "results"}
    print(json.dumps(printable, sort_keys=True))
    if not run.get("pass"):
        print("FAILED:ARC-0051-probe1 scenario did not reproduce")
        return 1
    if not ART.is_file():
        print("FAILED:ARC-0051-probe1 REFUTATION.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0051-probe1 self-declared {doc.get('state')}")
        return 1
    rec = (doc.get("scenario") or {}).get("reproduction") or {}
    rec_ok = (
        rec.get("estate_write_blocked_under_a7")
        and rec.get("estate_write_allowed_under_minimum")
        and rec.get("catalog_mention_blocked_under_a7")
        and rec.get("p0_holds_under_minimum")
    )
    if not rec_ok:
        print("FAILED:ARC-0051-probe1 REFUTATION reproduction flags false")
        return 1
    proc = doc.get("scenario", {}).get("procedure") or []
    if len(proc) < 4:
        print("FAILED:ARC-0051-probe1 procedure too short")
        return 1
    if not run.get("estate_write_blocked_under_a7"):
        print("FAILED:ARC-0051-probe1 Write was not denied by per-call approval")
        return 1
    if not run.get("estate_write_allowed_under_minimum"):
        print("FAILED:ARC-0051-probe1 minimum still blocked estate Write")
        return 1
    if not run.get("unsigned_plugin_denied_both"):
        print("FAILED:ARC-0051-probe1 P0 plugin fail-closed did not hold")
        return 1
    print(
        "blocked_write="
        f"{run.get('estate_write_blocked_under_a7')} "
        f"min_allow={run.get('estate_write_allowed_under_minimum')} "
        f"mention_overfire={run.get('catalog_mention_blocked_under_a7')} "
        f"p0={run.get('unsigned_plugin_denied_both')}"
    )
    print("SUCCESS:ARC-0051-probe1 blocking scenario reproduced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
