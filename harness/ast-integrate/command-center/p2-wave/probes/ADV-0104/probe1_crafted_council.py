#!/usr/bin/env python3
"""Probe 1: live crafted council under configured majority aggregation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

ART = H.REPO / H.OUTPUT_REL


def main() -> int:
    payload = H.probe1_payload()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload.get("pass"):
        print(
            "FAILED:ADV-0104-probe1 crafted council did not record "
            "evidence-free majority win with live engines"
        )
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0104-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if H.SENTINEL not in text:
        print("FAILED:ADV-0104-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != H.UNIT:
        print("FAILED:ADV-0104-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:ADV-0104-probe1 self-declared", doc.get("state"))
        return 1
    if H.CATALOG_PROBE1 not in text:
        print("FAILED:ADV-0104-probe1 catalog probe-1 text absent")
        return 1
    asym = doc.get("asymmetric") or {}
    if asym.get("winner") != payload["asymmetric_winner"]:
        print("FAILED:ADV-0104-probe1 artifact winner mismatch")
        return 1
    if not asym.get("evidence_free_majority_carried"):
        print("FAILED:ADV-0104-probe1 artifact missing evidence-free majority carry")
        return 1
    print("SUCCESS:ADV-0104-probe1 evidence-free majority carried the live council")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
