#!/usr/bin/env python3
"""Probe 2: miscalibrated fusion weight mutation control.

Mechanically different from probe 1 (which scores the production weights):
this probe holds the production calibrator fixed and flips the sign of both
fusion weights. At least one reliability bin must move outside the 0.15
tolerance, turning the calibration test red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PKG = REPO / "tools" / "router"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

from corpus import MUTANT_WEIGHTS, production_report  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0391.json"


def main() -> int:
    report = production_report()
    mut = report["mutation"]
    prod_out = mut["production_outlier_count"]
    mut_out = mut["mutant_outlier_count"]
    moved = bool(mut["mutant_moves_a_bin_outside_tolerance"])
    worse = report["mutant"]["accuracy"] < report["production"]["accuracy"]
    prod_clean = prod_out == 0

    receipt_ok = None
    if RECEIPT.is_file() and RECEIPT.stat().st_size > 0:
        doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
        published = doc.get("mutation_control") or {}
        receipt_ok = bool(published.get("mutant_moves_a_bin_outside_tolerance"))
        if published.get("mutant_outlier_count") is not None:
            receipt_ok = receipt_ok and int(published["mutant_outlier_count"]) == mut_out

    passed = prod_clean and moved and worse and (receipt_ok is not False)
    payload = {
        "probe": "probe2-miscalibrated-weight",
        "unit_id": "IMP-0391",
        "production_accuracy": round(report["production"]["accuracy"], 6),
        "mutant_accuracy": round(report["mutant"]["accuracy"], 6),
        "mutant_worse": worse,
        "production_outlier_count": prod_out,
        "mutant_outlier_count": mut_out,
        "mutant_named_outlier_bins": report["mutant"]["named_outlier_bins"],
        "mutant_weights": dict(MUTANT_WEIGHTS),
        "moved_outside_tolerance": moved,
        "receipt_present": RECEIPT.is_file(),
        "receipt_ok": receipt_ok,
        "pass": passed,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not prod_clean:
        print("FAILED:IMP-0391-probe2 production already outside tolerance")
        return 1
    if not moved:
        print("FAILED:IMP-0391-probe2 mutant weight did not move a bin outside 0.15")
        return 1
    if not worse:
        print("FAILED:IMP-0391-probe2 mutant accuracy did not drop")
        return 1
    if receipt_ok is False:
        print("FAILED:IMP-0391-probe2 receipt mutation_control does not match live")
        return 1
    print(
        f"production_outliers={prod_out} mutant_outliers={mut_out} "
        f"acc {report['production']['accuracy']:.3f} -> "
        f"{report['mutant']['accuracy']:.3f}"
    )
    print("SUCCESS:IMP-0391-probe2 mutant fusion weight turns calibration red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
