#!/usr/bin/env python3
"""Probe 1: independently recompute mirrored digests and check upstream provenance."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0106.json"


def main() -> int:
    live = S.run_digest_provenance()
    print(json.dumps({k: live[k] for k in sorted(live)}, sort_keys=True, default=str)[:4000])
    if not live.get("pass"):
        print("FAILED:IMP-0106-probe1 live digest/provenance scenario failed")
        return 1
    if not live.get("all_digests_equal"):
        print("FAILED:IMP-0106-probe1 recomputed digests do not match upstream")
        return 1
    if not live.get("all_sources_upstream"):
        print("FAILED:IMP-0106-probe1 provenance source is not upstream")
        return 1
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0106-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0106":
        print("FAILED:IMP-0106-probe1 unit_id", doc.get("unit_id"))
        return 1
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0106-probe1 self-declared {state}")
        return 1
    if "SUCCESS:IMP-0106" not in text:
        print("FAILED:IMP-0106-probe1 sentinel absent")
        return 1
    print("SUCCESS:IMP-0106-probe1 digests equal and provenance names upstream")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
