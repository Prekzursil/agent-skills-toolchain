#!/usr/bin/env python3
"""Probe 1: plant-orphan, detector-control, clean-zero, NOT-CHECKED, payload-dir lie."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import controls as C  # noqa: E402
import overclaim as O  # noqa: E402

ART = REPO / "command-center/receipts/REL-0007.json"


def main() -> int:
    run = C.run_all()
    for t in run["tests"]:
        print(f"{t['id']} result={t['result']} observed={t.get('observed')} {t.get('detail')}")
        if t["result"] != "PASS":
            print(f"FAILED:REL-0007-probe1 {t['id']}")
            return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:REL-0007-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        print("FAILED:REL-0007-probe1 receipt unparseable")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:REL-0007-probe1 receipt not an object")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:REL-0007-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:REL-0007" not in text:
        print("FAILED:REL-0007-probe1 sentinel absent")
        return 1
    body = O.payload(doc)
    if (
        doc.get("payload_used_as_orphan_verdict") is True
        or body.get("payload_used_as_orphan_verdict") is True
    ):
        print("FAILED:REL-0007-probe1 payload dir used as verdict")
        return 1
    print("SUCCESS:REL-0007-probe1 plant-orphan detector-control clean-zero not-checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
