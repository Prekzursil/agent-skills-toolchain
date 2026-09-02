#!/usr/bin/env python3
"""Probe 2: known-advisory liveness + exit-127 discipline (not lockfile diff).

Instrument: single-package POST /v1/query for lodash@4.17.11, empty-cache
negative, and a missing-binary subprocess classified as 127. Distinct from
probe 1 (querybatch set-diff).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scanner as S  # noqa: E402
import schema_check as SC  # noqa: E402

UNIT = "CNF-0112"
ART = REPO / "command-center/confirmation/CNF-0112-advisory-rescan.json"


def classify_zero_findings_vs_127() -> bool:
    """True when the classifier wrongly treats 127 as a clean scan."""
    return S.classify_scanner_exit(0) == S.classify_scanner_exit(127)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0112-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = SC.payload(doc)
    controls = {
        c.get("id"): c
        for c in (payload.get("controls") or [])
        if isinstance(c, dict)
    }
    recorded = controls.get("known-advisory-lodash-4.17.11") or {}
    if recorded.get("result") != "PASS" or not recorded.get("advisory_ids"):
        print("FAILED:CNF-0112-probe2 artifact control missing")
        return 1

    try:
        live = S.query_one(*S.KNOWN_ADVISORY_PKG)
    except RuntimeError as exc:
        print("FAILED:CNF-0112-probe2 database-not-live", exc)
        return 1
    vulns = live.get("vulns") or []
    ids = sorted(
        {str(v.get("id")) for v in vulns if isinstance(v, dict) and v.get("id")}
    )
    if not ids:
        print("FAILED:CNF-0112-probe2 known-advisory not reported")
        return 1

    cached = S.empty_cache_lookup(*S.KNOWN_ADVISORY_PKG)
    if cached:
        print("FAILED:CNF-0112-probe2 empty cache returned hits")
        return 1

    missing = S.run_missing_scanner()
    if missing.get("classification") != "scanner-not-installed":
        print("FAILED:CNF-0112-probe2 exit-127 classified as", missing)
        return 1
    if classify_zero_findings_vs_127():
        print("FAILED:CNF-0112-probe2 clean and 127 collapsed")
        return 1

    recorded_ids = set(recorded.get("advisory_ids") or [])
    if not recorded_ids.intersection(ids):
        print("FAILED:CNF-0112-probe2 control id drift", recorded_ids, ids)
        return 1

    out = {
        "probe": "probe2-liveness-control",
        "unit_id": UNIT,
        "advisory_ids": ids,
        "empty_cache_hits": len(cached),
        "missing_scanner": missing,
        "live": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"control lodash@4.17.11 ids={ids} cache_hits=0 "
        f"exit127={missing['exit_code']}"
    )
    print("SUCCESS:CNF-0112-probe2 liveness-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
