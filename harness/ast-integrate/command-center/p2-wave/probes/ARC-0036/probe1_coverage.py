#!/usr/bin/env python3
"""Probe 1: live named chaos + coverage exercised/12 with uncovered enumerated."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import cases as C  # noqa: E402
import schema_bind as SB  # noqa: E402

ART = REPO / "command-center/phase3/A5/TEST-PLAN.json"
DESIGN = REPO / "command-center/phase3/A5/DESIGN.json"


def main() -> int:
    live = C.run_all()
    for name, ok in live["checks"].items():
        print(f"{name}={ok}")
    if not live["pass"]:
        print(f"FAILED:ARC-0036-probe1 live {live['checks']}")
        return 1

    if DESIGN.is_file():
        print("FAILED:ARC-0036-probe1 A5 DESIGN.json present; this unit must not rebuild it")
        return 1

    if not ART.is_file():
        print("FAILED:ARC-0036-probe1 TEST-PLAN.json missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    body = SB.payload(doc)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0036-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:ARC-0036" not in text:
        print("FAILED:ARC-0036-probe1 sentinel absent")
        return 1

    art_cov = body.get("coverage") or doc.get("coverage") or {}
    live_cov = live["coverage"]
    if int(art_cov.get("exercised") or -1) != int(live_cov["exercised"]):
        print(
            f"FAILED:ARC-0036-probe1 coverage exercised drift "
            f"art={art_cov.get('exercised')} live={live_cov['exercised']}"
        )
        return 1
    if int(art_cov.get("total") or -1) != 12:
        print("FAILED:ARC-0036-probe1 coverage total is not 12")
        return 1
    art_unc = [
        (u.get("n"), u.get("id")) for u in (art_cov.get("uncovered") or [])
    ]
    live_unc = [(u["n"], u["id"]) for u in live_cov["uncovered"]]
    if art_unc != live_unc:
        print(f"FAILED:ARC-0036-probe1 uncovered drift art={art_unc} live={live_unc}")
        return 1

    chaos = body.get("chaos_cases") or doc.get("chaos_cases") or []
    if len(chaos) != 5:
        print(f"FAILED:ARC-0036-probe1 expected 5 named chaos cases, got {len(chaos)}")
        return 1
    live_named = {c["id"]: c for c in live["named_chaos"]}
    for row in chaos:
        cid = row.get("id")
        inj = str(row.get("injection_mechanism") or "")
        target = row.get("target_condition")
        if len(inj) < 8 or not isinstance(target, int):
            print(f"FAILED:ARC-0036-probe1 {cid} missing injection or target")
            return 1
        live_row = live_named.get(cid)
        if live_row is None:
            print(f"FAILED:ARC-0036-probe1 {cid} not in live named chaos")
            return 1
        if live_row["verdict"] != "INCOMPLETE":
            print(f"FAILED:ARC-0036-probe1 {cid} live verdict {live_row['verdict']}")
            return 1
        if not live_row["target_unsatisfied"]:
            print(f"FAILED:ARC-0036-probe1 {cid} target C{target} not UNSATISFIED")
            return 1
        if row.get("live_verdict") != live_row["verdict"]:
            print(f"FAILED:ARC-0036-probe1 {cid} artifact verdict drift")
            return 1
        print(
            f"{cid} target=C{target} verdict={live_row['verdict']} "
            f"unsatisfied={live_row['failing_condition_ids']}"
        )

    if live["healthy"]["verdict"] != "COMPLETE":
        print("FAILED:ARC-0036-probe1 healthy control is not COMPLETE")
        return 1
    print(
        f"coverage={live_cov['exercised']}/{live_cov['total']} "
        f"uncovered={live_cov['uncovered']}"
    )
    print("SUCCESS:ARC-0036-probe1 coverage named-chaos healthy-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
