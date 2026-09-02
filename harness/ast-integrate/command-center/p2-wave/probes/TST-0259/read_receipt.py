#!/usr/bin/env python3
"""Downstream consumer: parse catalog output_path and check planted-cast fields."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PATH = REPO / "command-center" / "receipts" / "TST-0259.json"


def main() -> int:
    doc = json.loads(PATH.read_text(encoding="utf-8"))
    report = doc["report"]
    if doc.get("unit_id") != "TST-0259" or doc.get("state") != "SUCCESS":
        print("FAILED:TST-0259-read unit/state")
        return 1
    if "SUCCESS:TST-0259" not in str(doc.get("sentinel") or ""):
        print("FAILED:TST-0259-read sentinel")
        return 1
    collapsed = report["collapsed"]
    differentiated = report["differentiated"]
    floor = float(report["floor"]["value"])
    if collapsed["panel"] != "FAIL" or differentiated["panel"] != "PASS":
        print("FAILED:TST-0259-read panels")
        return 1
    if not (collapsed["D"] < floor <= differentiated["D"]):
        print("FAILED:TST-0259-read floor relation")
        return 1
    sweep = report["sweep"]
    if sweep["n"] < 5 or sweep["independent_recompute_matched"] is not True:
        print("FAILED:TST-0259-read sweep")
        return 1
    print(f"READ_OK unit=TST-0259 bytes={PATH.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
