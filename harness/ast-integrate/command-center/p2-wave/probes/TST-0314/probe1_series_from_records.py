#!/usr/bin/env python3
"""Probe 1: loop metric series from decision records, not hand-tallied.

Catalog tests:
  * Loop metric series computed from decision records, not hand-tallied.
Evidence: per-iteration series with at least 5 iterations; a single
iteration is NOT-CHECKED.

The statistics reviewer independently recounts KEEP rates and Wilson
intervals from the raw records / per-case results.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

UNIT = "TST-0314"


def main() -> int:
    report = H.series_from_records_checks()
    print(json.dumps({k: report[k] for k in ("ok", "checks", "single") if k in report}, sort_keys=True))
    series = report.get("series") or {}
    n = series.get("n_iterations")
    status = series.get("status")
    if not report.get("ok"):
        print(f"FAILED:{UNIT}-probe1 series-from-records")
        print(json.dumps(report.get("checks"), indent=2)[:3000])
        return 1
    per = series.get("per_iteration") or []
    rates = [round(r["keep_rate"], 4) for r in per]
    print(
        f"n_iterations={n} status={status} keep_rate_series={rates} "
        f"source={series.get('source')} fingerprint={series.get('fingerprint', '')[:16]}"
    )
    print(
        f"SUCCESS:{UNIT}-probe1 loop metric series from decision records "
        f"n={n} CHECKED; single-iteration NOT-CHECKED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
