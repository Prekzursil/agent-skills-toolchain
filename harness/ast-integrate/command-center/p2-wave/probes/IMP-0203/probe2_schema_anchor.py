#!/usr/bin/env python3
"""Probe 2: certificate schema rejects a record with no evidence anchor.

Negative: missing evidence, summary-only evidence, empty anchor path.
Positive: current_record() is schema-valid (false-positive control).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import admit as A  # noqa: E402
import fixtures as F  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0203.json"


def _rejected(record: dict, label: str) -> int:
    errs = A.schema_errors(record)
    verdict = A.evaluate(
        record,
        live_corpus_version=F.CORPUS_CURRENT,
        live_spec_version=F.SPEC_CURRENT,
        now=F.NOW,
    )
    print(json.dumps({"case": label, "schema_errors": errs, "status": verdict["status"]}))
    if not errs:
        print(f"FAILED:IMP-0203-probe2 {label} was schema-accepted")
        return 1
    if verdict["status"] != A.INVALID:
        print(f"FAILED:IMP-0203-probe2 {label} status={verdict['status']} want=INVALID")
        return 1
    return 0


def main() -> int:
    good_errs = A.schema_errors(F.current_record())
    if good_errs:
        print("FAILED:IMP-0203-probe2 current_record schema-invalid")
        print(json.dumps(good_errs, indent=2))
        return 1
    good = A.evaluate(
        F.current_record(),
        live_corpus_version=F.CORPUS_CURRENT,
        live_spec_version=F.SPEC_CURRENT,
        now=F.NOW,
    )
    if good["status"] != A.VALID:
        print(f"FAILED:IMP-0203-probe2 good status={good['status']}")
        return 1
    print("good_record status=VALID schema_errors=0")

    if _rejected(F.no_evidence_record(), "no-evidence"):
        return 1
    if _rejected(F.no_anchor_record(), "summary-only-no-anchor"):
        return 1
    if _rejected(F.empty_anchor_path_record(), "empty-anchor-path"):
        return 1

    if not ART.is_file():
        print("FAILED:IMP-0203-probe2 catalog receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0203" not in text:
        print("FAILED:IMP-0203-probe2 sentinel absent")
        return 1

    print("fired_on_bad=True silent_on_good=True")
    print("SUCCESS:IMP-0203-probe2 schema rejects no evidence anchor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
