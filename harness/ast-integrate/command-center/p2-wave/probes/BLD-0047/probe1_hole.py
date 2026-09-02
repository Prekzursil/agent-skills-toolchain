#!/usr/bin/env python3
"""Probe 1: reproduce the known bare-invocation hole on validate.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0047.json"


def main() -> int:
    hole = E.reproduce_known_hole()
    print(json.dumps({k: hole[k] for k in hole if k not in {"bare_tail", "armed_tail"}}, sort_keys=True))
    print("bare_tail=" + hole["bare_tail"].replace("\n", " | ")[:240])
    print("armed_tail=" + hole["armed_tail"].replace("\n", " | ")[:240])
    if not hole["pass"]:
        print(
            "FAILED:BLD-0047-probe1 defaults-deletion "
            f"bare_exit={hole['bare_exit']} armed_exit={hole['armed_exit']}"
        )
        return 1
    if not ART.is_file():
        print("FAILED:BLD-0047-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:BLD-0047-probe1 self-declared", doc.get("state"))
        return 1
    if "SUCCESS:BLD-0047" not in text:
        print("FAILED:BLD-0047-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != "BLD-0047":
        print("FAILED:BLD-0047-probe1 unit_id")
        return 1
    known = doc.get("known_hole") or {}
    if known.get("bare_exit") != 0 or known.get("armed_exit") == 0:
        print("FAILED:BLD-0047-probe1 receipt hole mismatch", known)
        return 1
    print("SUCCESS:BLD-0047-probe1 known-hole bare=0 armed!=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
