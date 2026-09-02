#!/usr/bin/env python3
"""Probe 1: skew matrix — every supported (producer, consumer) pair is exercised or NOT-CHECKED."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import golden as G  # noqa: E402
import negotiate as N  # noqa: E402

REPORT = REPO / G.OUT_REL
FORBIDDEN_STATUS = frozenset({"PASS", "SUPPORTED", "INFERRED", "OK", "GREEN"})


def _catalog_cells(matrix: list[dict]) -> list[dict]:
    return [c for c in matrix if c.get("artifact_class") == N.CATALOG_CLASS]


def main() -> int:
    if not REPORT.is_file() or REPORT.stat().st_size <= 0:
        print("FAILED:ARC-0103-probe1 report absent")
        return 1
    doc = json.loads(REPORT.read_text(encoding="utf-8"))
    body = G.report_body(doc)
    live_cat = G.load_catalog()
    live_matrix = G.catalog_skew_matrix(live_cat) + G.other_class_cells()
    reported = body.get("skew_matrix") or []
    if not isinstance(reported, list) or len(reported) < 4:
        print(f"FAILED:ARC-0103-probe1 matrix too small n={len(reported) if isinstance(reported, list) else 0}")
        return 1

    live_index = {
        (c["artifact_class"], c["producer_version"], c["consumer_version"]): c
        for c in live_matrix
    }
    report_index = {
        (c["artifact_class"], c["producer_version"], c["consumer_version"]): c
        for c in reported
        if isinstance(c, dict)
    }

    required = [(N.CATALOG_CLASS, p, c) for p in (1, 2) for c in (1, 2)]
    for key in required:
        if key not in report_index:
            print(f"FAILED:ARC-0103-probe1 missing catalog cell {key}")
            return 1
        if key not in live_index:
            print(f"FAILED:ARC-0103-probe1 live missing cell {key}")
            return 1
        rstat = str(report_index[key].get("status") or "")
        lstat = str(live_index[key].get("status") or "")
        if rstat != lstat:
            print(f"FAILED:ARC-0103-probe1 stale {key} report={rstat} live={lstat}")
            return 1
        if report_index[key].get("inferred") is True:
            print(f"FAILED:ARC-0103-probe1 inferred cell {key}")
            return 1
        if rstat in FORBIDDEN_STATUS:
            print(f"FAILED:ARC-0103-probe1 cell {key} status={rstat} looks like a pass")
            return 1

    accept12 = report_index[(N.CATALOG_CLASS, 1, 2)].get("status")
    refuse21 = report_index[(N.CATALOG_CLASS, 2, 1)].get("status")
    accept11 = report_index[(N.CATALOG_CLASS, 1, 1)].get("status")
    accept22 = report_index[(N.CATALOG_CLASS, 2, 2)].get("status")
    if accept12 != "EXERCISED-ACCEPT":
        print(f"FAILED:ARC-0103-probe1 (1,2) previous->current status={accept12}")
        return 1
    if refuse21 != "EXERCISED-REFUSE":
        print(f"FAILED:ARC-0103-probe1 (2,1) forward-incompatible status={refuse21}")
        return 1
    if accept11 != "EXERCISED-ACCEPT":
        print(f"FAILED:ARC-0103-probe1 (1,1) status={accept11}")
        return 1
    if accept22 != "EXERCISED-ACCEPT":
        print(f"FAILED:ARC-0103-probe1 (2,2) live status={accept22}")
        return 1

    not_checked = [c for c in reported if str(c.get("status") or "") == "NOT-CHECKED"]
    for cell in not_checked:
        if cell.get("inferred") is True:
            print("FAILED:ARC-0103-probe1 NOT-CHECKED cell marked inferred")
            return 1

    if "SUCCESS:ARC-0103" not in json.dumps(doc):
        print("FAILED:ARC-0103-probe1 sentinel absent")
        return 1

    print(
        "catalog_cells=4 "
        f"(1,1)={accept11} (1,2)={accept12} (2,1)={refuse21} (2,2)={accept22} "
        f"not_checked={len(not_checked)} inferred=0 live_match=True"
    )
    print("SUCCESS:ARC-0103-probe1 skew matrix completeness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
