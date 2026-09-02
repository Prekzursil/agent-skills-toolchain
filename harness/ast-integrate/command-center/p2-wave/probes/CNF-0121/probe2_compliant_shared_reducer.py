#!/usr/bin/env python3
"""Probe 2: compliant control passes, and audit uses the fan-in reducer object."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import emit_audit  # noqa: E402
import fanin  # noqa: E402
import shared_reducer  # noqa: E402
from fanin import evaluate_condition_9  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0121-reviewer-condition-audit.json"
FIXTURE = HERE / "fixtures" / "compliant.json"


def main() -> int:
    if evaluate_condition_9 is not shared_reducer.evaluate_condition_9:
        print("FAILED:CNF-0121-probe2 fan-in is not the shared reducer")
        return 1
    if fanin.evaluate_condition_9 is not shared_reducer.evaluate_condition_9:
        print("FAILED:CNF-0121-probe2 fanin module symbol forked")
        return 1
    if emit_audit.EVALUATE_C9 is not shared_reducer.evaluate_condition_9:
        print("FAILED:CNF-0121-probe2 audit EVALUATE_C9 is a separate rule")
        return 1
    receipt = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = evaluate_condition_9(receipt)
    printable = {
        "probe": "probe2-compliant-shared-reducer",
        "unit_id": "CNF-0121",
        "outcome": result.get("outcome"),
        "classification": result.get("classification"),
        "same_object_fanin_reducer": True,
        "same_object_audit_reducer": True,
        "reducer_anchor": result.get("reducer_anchor"),
    }
    print(json.dumps(printable, sort_keys=True))
    if result.get("outcome") != "PASS":
        print(f"FAILED:CNF-0121-probe2 compliant control outcome={result.get('outcome')}")
        print(result.get("reason"))
        return 1
    if result.get("classification") != "independent-pass":
        print(f"FAILED:CNF-0121-probe2 classification={result.get('classification')}")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0121-probe2 audit artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0121-probe2 self-declared {doc.get('state')}")
        return 1
    if (
        report.get("compliant_control_passed") is not True
        and doc.get("compliant_control_passed") is not True
    ):
        print("FAILED:CNF-0121-probe2 artifact compliant_control_passed is not true")
        return 1
    reducer = report.get("reducer") if isinstance(report.get("reducer"), dict) else doc.get("reducer")
    if not isinstance(reducer, dict) or reducer.get("same_object_as_fanin") is not True:
        print("FAILED:CNF-0121-probe2 artifact did not record shared reducer identity")
        return 1
    sentinel = (
        "SUCCESS:CNF-0121 emitted only when the artifact at output_path exists, is "
        "non-empty, parses against output_schema, and every receipt has a condition-9 "
        "result produced by the shared reducer and the compliant control passed. Any "
        "other terminal state is FAILED:CNF-0121 <classification> with the diagnostic "
        "tail attached."
    )
    if sentinel not in text:
        print("FAILED:CNF-0121-probe2 sentinel absent")
        return 1
    receipts = report.get("receipts") or doc.get("receipts") or []
    for row in receipts:
        c9 = row.get("condition_9") or {}
        if c9.get("reducer_anchor") != result.get("reducer_anchor"):
            print("FAILED:CNF-0121-probe2 live row not produced by shared reducer")
            return 1
        if "reviewer_identity" not in row or "independence_verdict" not in row:
            print("FAILED:CNF-0121-probe2 receipt missing required evidence fields")
            return 1
    print("SUCCESS:CNF-0121-probe2 compliant control and shared reducer identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
