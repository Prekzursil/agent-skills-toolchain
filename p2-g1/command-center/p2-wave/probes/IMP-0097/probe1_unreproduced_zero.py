"""IMP-0097 probe1: an UNREPRODUCED benchmark record contributes exactly zero.

Signal 1 (catalog): zero contribution is proven by score EQUALITY - the recomputed
total with the record present equals the total with it removed. A rule stated in
docs but not reflected in the arithmetic is an overclaim.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
MKT = REPO / "tools" / "marketplace"
sys.path.insert(0, str(MKT))

from benchmark_gaming import contribution, score_with_benchmarks, score_without_record  # noqa: E402
from scenario import load_scenario  # noqa: E402


def main() -> int:
    measurements, records, provenance, _raw = load_scenario()
    full = score_with_benchmarks(measurements, records, provenance)
    checks = {}
    equalities = []
    for rec in records:
        c = contribution(rec, provenance)
        without = score_without_record(measurements, records, provenance, rec.record_id)
        zero = c == 0.0
        equal = full.total == without.total
        equalities.append({
            "record_id": rec.record_id,
            "claimed_delta": rec.claimed_delta,
            "contribution": c,
            "full_total": full.total,
            "without_total": without.total,
            "contributes_zero": zero,
            "score_equal_without": equal,
        })
        if rec.record_id == "rec.independent.reproduced":
            # the negative control: reproduced by an independent executor, third-party case set
            checks["good_record_" + rec.record_id] = (c != 0.0) and (not equal)
        else:
            # unreproduced, publisher-only, failed-independent AND self-authored all score zero
            checks["zero_record_" + rec.record_id] = zero and equal

    neg = [r for r in equalities if r["record_id"] == "rec.independent.reproduced"][0]
    raised_by = round(neg["full_total"] - neg["without_total"], 9)
    checks["negative_control_raises"] = raised_by > 0
    checks["raised_matches_claimed"] = raised_by == 1.5

    out = {
        "unit_id": "IMP-0097",
        "probe": "probe1-unreproduced-zero",
        "base": full.base,
        "full_total": full.total,
        "equalities": equalities,
        "negative_control": {"record_id": "rec.independent.reproduced", "raised_by": raised_by},
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, indent=1))
    if all(checks.values()):
        print("SUCCESS:IMP-0097-probe1 every unreproduced, publisher-only and failed record scores exactly zero by score equality; the reproduced independent record raises the total by its claimed delta in the same run")
        return 0
    print("FAILED:IMP-0097-probe1")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
