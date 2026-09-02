#!/usr/bin/env python3
"""Probe 1: live artifact has 13 bucket rows and 21 phase rows; no omissions."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from coverage import compute_coverage  # noqa: E402
from graph import EXPECTED_BUCKET_IDS  # noqa: E402

ART = REPO / "command-center/receipts/SYN-0032.json"


def main() -> int:
    live = compute_coverage(REPO)
    buckets = live["bucket_table"]
    phases = live["phase_table"]
    print(f"live_buckets={len(buckets)} live_phases={len(phases)}")
    if len(buckets) != 13:
        print(f"FAILED:SYN-0032-probe1 live bucket rows {len(buckets)} != 13")
        return 1
    if len(phases) != 21:
        print(f"FAILED:SYN-0032-probe1 live phase rows {len(phases)} != 21")
        return 1
    got_b = [r["id"] for r in buckets]
    if got_b != list(EXPECTED_BUCKET_IDS):
        print(f"FAILED:SYN-0032-probe1 bucket ids {got_b}")
        return 1
    got_p = [r["id"] for r in phases]
    if len(set(got_p)) != 21:
        print(f"FAILED:SYN-0032-probe1 duplicate or missing phases {got_p}")
        return 1
    if "16" not in got_p:
        print("FAILED:SYN-0032-probe1 phase 16 omitted")
        return 1
    p16 = next(r for r in phases if r["id"] == "16")
    if p16["has_allocation_bucket"] is not False:
        print("FAILED:SYN-0032-probe1 phase 16 marked as having a bucket")
        return 1
    funded = live["phase_16_funded_by"]
    note = str(funded.get("note") or "")
    if not funded.get("unit_ids"):
        print("FAILED:SYN-0032-probe1 funded-by unit_ids missing")
        return 1
    if "Phase 16" not in note or "funded" not in note.lower():
        print("FAILED:SYN-0032-probe1 funded-by note missing")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:SYN-0032-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:SYN-0032-probe1 self-declared {doc.get('state')}")
        return 1
    art_b = [r["id"] for r in doc.get("bucket_table") or []]
    art_p = [r["id"] for r in doc.get("phase_table") or []]
    if art_b != got_b:
        print(f"FAILED:SYN-0032-probe1 artifact bucket rows drifted {art_b}")
        return 1
    if art_p != got_p:
        print(f"FAILED:SYN-0032-probe1 artifact phase rows drifted {art_p}")
        return 1
    sentinel = str(doc.get("sentinel") or "")
    if not sentinel or sentinel not in text:
        print("FAILED:SYN-0032-probe1 sentinel absent from artifact")
        return 1
    print(f"artifact_buckets={art_b}")
    print(f"artifact_phases={art_p}")
    print("SUCCESS:SYN-0032-probe1 row completeness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
