#!/usr/bin/env python3
"""Probe 1: attached record is complete; missing fingerprint is rejected."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.benchmark_evidence import EvidenceError, validate_record  # noqa: E402

RECEIPT = REPO / "command-center/receipts/IMP-0096.json"


def main() -> int:
    if not RECEIPT.is_file():
        print("FAILED:IMP-0096-probe1 receipt missing")
        return 1
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0096-probe1 self-declared {doc.get('state')}")
        return 1
    text = RECEIPT.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0096" not in text:
        print("FAILED:IMP-0096-probe1 sentinel absent")
        return 1
    record = doc.get("benchmark_record")
    if not isinstance(record, dict):
        print("FAILED:IMP-0096-probe1 no benchmark_record")
        return 1
    try:
        validate_record(record)
    except EvidenceError as exc:
        print(f"FAILED:IMP-0096-probe1 record rejected: {exc}")
        return 1
    required = [
        "harness_version",
        "case_set_id",
        "environment_fingerprint",
        "reproduction_command",
        "commit_sha",
        "run_id",
    ]
    for key in required:
        if not record.get(key):
            print(f"FAILED:IMP-0096-probe1 empty field {key}")
            return 1
    mutant = copy.deepcopy(record)
    del mutant["environment_fingerprint"]
    rejected = False
    try:
        validate_record(mutant)
    except EvidenceError:
        rejected = True
    if not rejected:
        print("FAILED:IMP-0096-probe1 missing fingerprint accepted")
        return 1
    out = {
        "probe": "probe1-record-completeness",
        "unit_id": "IMP-0096",
        "validated": True,
        "negative_control_missing_fingerprint_rejected": True,
        "run_id": record["run_id"],
        "case_set_id": record["case_set_id"],
        "harness_version": record["harness_version"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0096-probe1 record completeness and fingerprint reject")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
