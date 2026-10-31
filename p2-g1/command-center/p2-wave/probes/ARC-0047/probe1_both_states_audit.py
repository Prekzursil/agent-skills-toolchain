#!/usr/bin/env python3
"""Probe 1: both-states audit table, use-versus-mention, live re-run vs artifact.

Every found gate must have broken and good outcomes. Silent-in-both is
MEASURING-NOTHING. Text-matching gates get a mention document. A7 DESIGN
must remain absent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import audit as AU  # noqa: E402
import events as E  # noqa: E402
import gates as G  # noqa: E402

ART = REPO / "command-center/phase3/A7/FAILURE-MODES.json"


def main() -> int:
    table = AU.run_audit()
    checks = table.get("checks") or {}
    for name, ok in checks.items():
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:ARC-0047-probe1 {name}")
            return 1
    if not table.get("pass"):
        print("FAILED:ARC-0047-probe1 audit failed")
        return 1

    _design7 = REPO / "command-center/phase3/A7/DESIGN.json"
    if _design7.is_file() and _design7.stat().st_mtime > Path(__file__).stat().st_mtime:
        print(
            "FAILED:ARC-0047-probe1 A7 DESIGN.json rebuilt during this wave "
            "(mtime newer than the staged gate); ADV rebuild"
        )
        return 1

    if G.except_pass_gate(E.EXCEPT_ON_USE) is not False:
        print("FAILED:ARC-0047-probe1 except-pass should return PASS on eval error")
        return 1

    if not ART.is_file():
        print("FAILED:ARC-0047-probe1 FAILURE-MODES.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0047-probe1 self-declared {doc.get('state')}")
        return 1
    if bool(doc.get("a7_design_present")) != _design7.is_file():
        print("FAILED:ARC-0047-probe1 artifact a7_design_present disagrees with tree")
        return 1

    live_rows = {r["id"]: r for r in table["rows"]}
    art_audit = doc.get("gate_audit") or {}
    art_rows = {r["id"]: r for r in (art_audit.get("rows") or [])}
    if set(live_rows) != set(art_rows):
        print(f"FAILED:ARC-0047-probe1 gate id drift live={sorted(live_rows)} art={sorted(art_rows)}")
        return 1
    for gid, live in live_rows.items():
        art = art_rows[gid]
        if live["classification"] != art.get("classification"):
            print(f"FAILED:ARC-0047-probe1 {gid} classification drift")
            return 1
        if live["broken"]["fired"] != art["broken"]["fired"]:
            print(f"FAILED:ARC-0047-probe1 {gid} broken drift")
            return 1
        if live["good"]["fired"] != art["good"]["fired"]:
            print(f"FAILED:ARC-0047-probe1 {gid} good drift")
            return 1
        print(
            f"{gid} broken={live['broken']['fired']} good={live['good']['fired']} "
            f"class={live['classification']}"
        )

    if "G-SILENT" not in (art_audit.get("measuring_nothing") or []):
        print("FAILED:ARC-0047-probe1 G-SILENT not classified MEASURING-NOTHING")
        return 1
    if "G-TEXT-PAYLOAD" not in (art_audit.get("fail_open") or []):
        print("FAILED:ARC-0047-probe1 G-TEXT-PAYLOAD not FAIL-OPEN")
        return 1
    if "G-TOOL-VERB" not in (art_audit.get("mention_ok") or []):
        print("FAILED:ARC-0047-probe1 verb gate did not pass use-vs-mention")
        return 1
    if "G-TEXT-PAYLOAD" not in (art_audit.get("mention_fail") or []):
        print("FAILED:ARC-0047-probe1 text gate did not fail use-vs-mention")
        return 1
    if "SUCCESS:ARC-0047" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0047-probe1 sentinel absent")
        return 1
    print(
        f"gates={table['gate_count']} fail_open={table['fail_open']} "
        f"measuring_nothing={table['measuring_nothing']}"
    )
    print("SUCCESS:ARC-0047-probe1 both-states audit use-vs-mention live-vs-artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
