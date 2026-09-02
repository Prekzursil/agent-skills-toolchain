#!/usr/bin/env python3
"""Probe 2: reproduction command actually runs in a clean env within tolerance."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.benchmark_evidence import (  # noqa: E402
    evaluate_evidence,
    validate_record,
)

RECEIPT = REPO / "command-center/receipts/IMP-0096.json"


def main() -> int:
    if not RECEIPT.is_file():
        print("FAILED:IMP-0096-probe2 receipt missing")
        return 1
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    record = doc.get("benchmark_record")
    if not isinstance(record, dict):
        print("FAILED:IMP-0096-probe2 no benchmark_record")
        return 1
    evaluation = evaluate_evidence(record, repo=REPO)
    repro = evaluation.get("reproduction") or {}
    if not evaluation.get("is_evidence"):
        print("FAILED:IMP-0096-probe2 not evidence")
        print(json.dumps(evaluation, sort_keys=True, default=str)[:3000])
        return 1
    if repro.get("status") != "REPRODUCED":
        print("FAILED:IMP-0096-probe2 status", repro.get("status"))
        return 1
    if repro.get("returncode") != 0:
        print("FAILED:IMP-0096-probe2 returncode", repro.get("returncode"))
        return 1
    if not repro.get("metric_within_tolerance"):
        print("FAILED:IMP-0096-probe2 outside tolerance")
        return 1
    broken = copy.deepcopy(record)
    broken["reproduction_command"] = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "tools/marketplace/harness/run_case_set.py --case-set "
        "tools/marketplace/fixtures/missing-case-set.json --json"
    )
    validate_record(broken)
    bad = evaluate_evidence(broken, repo=REPO)
    if bad.get("is_evidence"):
        print("FAILED:IMP-0096-probe2 unreproducible record counted as evidence")
        return 1
    if (bad.get("reproduction") or {}).get("status") != "UNREPRODUCED":
        print("FAILED:IMP-0096-probe2 expected UNREPRODUCED")
        return 1
    recorded = (doc.get("evidence") or {}).get("reproduction") or {}
    if recorded.get("status") != "REPRODUCED":
        print("FAILED:IMP-0096-probe2 receipt did not record a live reproduction")
        return 1
    out = {
        "probe": "probe2-reproduction-runs",
        "unit_id": "IMP-0096",
        "status": repro["status"],
        "observed_metric": repro["observed_metric"],
        "claimed_metric": repro["claimed_metric"],
        "checksum_match": repro["checksum_match"],
        "unreproducible_is_not_evidence": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0096-probe2 reproduction command ran within tolerance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
