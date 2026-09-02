#!/usr/bin/env python3
"""Probe 1: force every catalog fallback kind; artifact survives; live injection."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import inject  # noqa: E402

ART = REPO / "command-center" / "receipts" / "BLD-0026.json"


def main() -> int:
    fx = inject.force_fixture_kinds()
    live = inject.force_live()
    loud = [r for r in fx["results"] if r.get("classification") == "LOUD"]
    print(f"fixture_loud={len(loud)} fixture_forced={fx['forced']}")
    print(f"live_forced={len(live['forced'])} unreachable={live['unreachable_by_injection']}")
    if len(loud) < 5:
        print("FAILED:BLD-0026-probe1 fewer than 5 LOUD kinds forced")
        return 1
    if not all(r.get("artifact_survived") for r in fx["results"] if "artifact_survived" in r):
        print("FAILED:BLD-0026-probe1 work artifact did not survive")
        return 1
    if not any(r.get("classification") == "LOUD" for r in live["forced"]):
        print("FAILED:BLD-0026-probe1 live resolver was not LOUD")
        return 1
    if not ART.is_file():
        print("FAILED:BLD-0026-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:BLD-0026-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:BLD-0026" not in text:
        print("FAILED:BLD-0026-probe1 sentinel absent")
        return 1
    print("SUCCESS:BLD-0026-probe1 force-fallback artifact-preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
