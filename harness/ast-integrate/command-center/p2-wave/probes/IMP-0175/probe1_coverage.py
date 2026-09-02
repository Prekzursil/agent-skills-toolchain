#!/usr/bin/env python3
"""Probe 1: cell coverage == |components|^2, computed, with a drop-one mutant.

Mechanically different from probe 2 (which inspects FORBIDDEN reason tokens).
This probe counts ordered pairs. A map that merely has n^2 rows but repeats a
pair and omits another must fail unique_pair_count.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from foundry.compat_map import (  # noqa: E402
    build_map,
    coverage_report,
    drop_one_cell,
)

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0175.json"
SIDECAR = REPO / "command-center" / "foundry" / "merge-compatibility-map.json"


def _load_published() -> dict | None:
    for path in (SIDECAR, RECEIPT):
        if not path.is_file() or path.stat().st_size <= 0:
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        if path == RECEIPT:
            report = doc.get("report") or doc.get("merge_compatibility_map")
            if isinstance(report, dict) and report.get("cells"):
                return report
            continue
        if doc.get("cells"):
            return doc
    return None


def main() -> int:
    live = build_map(repo=REPO)
    cov_live = coverage_report(live)
    n = live["component_count"]
    src = live["components"][0]["id"]
    dst = live["components"][-1]["id"]
    mutant = drop_one_cell(live, src, dst)
    cov_mutant = coverage_report(mutant)

    published = _load_published()
    cov_pub = coverage_report(published) if published else None
    receipt_text = RECEIPT.read_text(encoding="utf-8") if RECEIPT.is_file() else ""
    receipt_ok = None
    if RECEIPT.is_file():
        receipt_ok = (
            "SUCCESS:IMP-0175" in receipt_text
            and cov_pub is not None
            and cov_pub["coverage_ok"] is True
            and cov_pub["n_squared"] == n * n
        )

    detector_both_states = cov_live["coverage_ok"] is True and cov_mutant["coverage_ok"] is False
    payload = {
        "probe": "probe1-coverage",
        "unit_id": "IMP-0175",
        "component_count": n,
        "n_squared": n * n,
        "cell_count": cov_live["cell_count"],
        "unique_pair_count": cov_live["unique_pair_count"],
        "coverage_ok": cov_live["coverage_ok"],
        "missing_pairs": cov_live["missing_pairs"],
        "extra_pairs": cov_live["extra_pairs"],
        "mutant_dropped": f"{src}->{dst}",
        "mutant_coverage_ok": cov_mutant["coverage_ok"],
        "mutant_missing": cov_mutant["missing_pairs"],
        "detector_fires_on_missing_cell": cov_mutant["coverage_ok"] is False,
        "detector_silent_on_complete_map": cov_live["coverage_ok"] is True,
        "receipt_present": RECEIPT.is_file(),
        "receipt_coverage_ok": None if cov_pub is None else cov_pub["coverage_ok"],
        "receipt_ok": receipt_ok,
        "component_origin": live.get("component_origin"),
        "pass": detector_both_states
        and cov_live["cell_count"] == n * n
        and (receipt_ok is not False),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not cov_live["coverage_ok"]:
        print("FAILED:IMP-0175-probe1 live map is not exhaustive")
        return 1
    if cov_mutant["coverage_ok"]:
        print("FAILED:IMP-0175-probe1 coverage detector silent after dropping a cell")
        return 1
    if receipt_ok is False:
        print("FAILED:IMP-0175-probe1 published map coverage mismatch")
        return 1
    print(
        f"n={n} n^2={n*n} cells={cov_live['cell_count']} "
        f"mutant_missing={cov_mutant['missing_pairs']}"
    )
    print("SUCCESS:IMP-0175-probe1 cell coverage == |components|^2 (computed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
