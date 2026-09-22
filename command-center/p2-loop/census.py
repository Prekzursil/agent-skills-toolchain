#!/usr/bin/env python3
"""P2 hard-bar census: count catalog units with green SUCCESS receipts.

Green = output_path exists, non-empty, JSON ``state==SUCCESS`` and no ``failure`` block.
Exit 0 only when green_SUCCESS == catalog_units (owner hard bar).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"


def classify(path: Path) -> str:
    if not path.is_file() or path.stat().st_size == 0:
        return "MISSING_OR_EMPTY"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "NO_STATE"
    st = doc.get("state")
    if not st:
        return "NO_STATE"
    if st == "SUCCESS" and doc.get("failure"):
        return "SUCCESS_WITH_FAILURE_BLOCK"
    if st == "SUCCESS":
        return "SUCCESS"
    if st == "BLOCKED":
        return "BLOCKED"
    return f"OTHER:{st}"


def census() -> dict:
    units = json.loads(CATALOG.read_text(encoding="utf-8"))["work_units"]
    hist: Counter[str] = Counter()
    for u in units:
        hist[classify(REPO / u["output_path"])] += 1
    green = hist["SUCCESS"]
    return {
        "catalog_units": len(units),
        "green_SUCCESS": green,
        "nongreen": len(units) - green,
        "all_green": green == len(units),
        "owner_hard_bar_met": green == len(units),
        "state_histogram": dict(hist),
        "result": "PASS" if green == len(units) else "FAIL",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json-out", type=Path, help="Write census JSON here")
    args = ap.parse_args()
    report = census()
    text = json.dumps(report, indent=2) + "\n"
    sys.stdout.write(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text, encoding="utf-8")
    return 0 if report["owner_hard_bar_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
