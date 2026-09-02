#!/usr/bin/env python3
"""Probe 1: blast-radius classification with reversal cost.

Every decision must have stance, computed blast radius, reversal cost, and
worst-case. Live generate() file count and catalog Write-without-gate must
match the artifact. Detector control: known review field fires; live is silent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import decisions as D  # noqa: E402

ART = REPO / "command-center/phase3/A8/SECURITY.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:ARC-0055-probe1 SECURITY.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0055-probe1 self-declared {doc.get('state')}")
        return 1
    live = D.classify(REPO)
    if not live["classification_complete"]:
        print(f"FAILED:ARC-0055-probe1 incomplete {live['missing_fields']}")
        return 1
    if live["a8_design_present"]:
        print("FAILED:ARC-0055-probe1 A8 DESIGN present; this unit must not rebuild it")
        return 1
    if live["defaulted_count"] < 1 or live["explicit_count"] < 1:
        print("FAILED:ARC-0055-probe1 need both DEFAULTED and EXPLICIT")
        return 1
    art_br = doc.get("blast_radius") or {}
    live_files = int(live["one_click"]["files_written_count"])
    live_write = int(live["catalog"]["write_without_owner_gate"])
    if int(art_br.get("marketplace_files_written_on_one_click") or 0) != live_files:
        print("FAILED:ARC-0055-probe1 marketplace file count != live generate()")
        return 1
    if int(art_br.get("catalog_write_without_owner_gate") or 0) != live_write:
        print("FAILED:ARC-0055-probe1 write-without-gate != live catalog")
        return 1
    if live_files < 1 or live_write < 1:
        print("FAILED:ARC-0055-probe1 nonpositive blast counts")
        return 1
    mkt = live["marketplace_schema"]
    if mkt["detector_fires_on_known_review_field"] is not True:
        print("FAILED:ARC-0055-probe1 detector control did not fire on fixture")
        return 1
    if mkt["detector_silent_on_live"] is not True:
        print("FAILED:ARC-0055-probe1 live schema unexpectedly has review keys")
        return 1
    if live["one_click"]["owner_prompts_invoked"] != 0:
        print("FAILED:ARC-0055-probe1 one-click invoked a prompt")
        return 1
    rec = (doc.get("scenario") or {}).get("reproduction") or {}
    if rec.get("files_written") != live_files:
        print("FAILED:ARC-0055-probe1 scenario files_written != live")
        return 1
    art_ids = [d.get("id") for d in (doc.get("decisions") or [])]
    live_ids = [d.get("id") for d in live["decisions"]]
    if art_ids != live_ids:
        print(f"FAILED:ARC-0055-probe1 decision ids drift {art_ids} vs {live_ids}")
        return 1
    for d in doc.get("decisions") or []:
        if not str(d.get("reversal_cost") or "").strip():
            print(f"FAILED:ARC-0055-probe1 {d.get('id')} missing reversal_cost")
            return 1
        if (d.get("blast_radius") or {}).get("computed_not_asserted") is not True:
            print(f"FAILED:ARC-0055-probe1 {d.get('id')} blast not computed")
            return 1
    if "SUCCESS:ARC-0055" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0055-probe1 sentinel absent")
        return 1
    print(
        f"files_written={live_files} write_no_oa={live_write} "
        f"defaulted={live['defaulted_count']} explicit={live['explicit_count']} "
        f"detector_fixture={mkt['fixture_review_like_count']} "
        f"detector_live={mkt['live_review_like_count']}"
    )
    print("SUCCESS:ARC-0055-probe1 blast-radius classification and reversal cost")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
