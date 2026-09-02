#!/usr/bin/env python3
"""Probe 2: NOT-APPLICABLE without justification fails; silent pass and permanent block fail."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import stopping_predicate as SP  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0457.json"


def _has(errors: list[str], needle: str) -> bool:
    return any(needle in e for e in errors)


def main() -> int:
    unjustified = SP.planted_unjustified_na_errors()
    silent = SP.planted_silent_pass_errors()
    blocked = SP.planted_permanent_block_errors()
    good = SP.evaluate_all("PR-ONLY")
    canary = SP.evaluate_all("PRIVATE-CANARY")

    planted = {
        "unjustified_na_fails": _has(
            unjustified, "not-applicable-without-justification"
        ),
        "silent_pass_fails": _has(silent, "inapplicable-as-silent-pass"),
        "permanent_block_fails": _has(blocked, "inapplicable-as-permanent-block"),
        "good_pr_only_valid": good["valid"] is True,
        "good_canary_valid": canary["valid"] is True,
        "unjustified_errors": unjustified,
        "silent_errors": silent,
        "block_errors": blocked,
    }
    print(
        json.dumps(
            {
                "probe": "probe2-justification-required",
                "unit_id": "IMP-0457",
                "unjustified_na_fails": planted["unjustified_na_fails"],
                "silent_pass_fails": planted["silent_pass_fails"],
                "permanent_block_fails": planted["permanent_block_fails"],
                "good_pr_only_valid": planted["good_pr_only_valid"],
                "good_canary_valid": planted["good_canary_valid"],
                "unjustified_error_count": len(unjustified),
                "silent_error_count": len(silent),
                "block_error_count": len(blocked),
            },
            sort_keys=True,
        )
    )
    if not planted["unjustified_na_fails"]:
        print("FAILED:IMP-0457-probe2 unjustified N/A was accepted")
        return 1
    if not planted["silent_pass_fails"]:
        print("FAILED:IMP-0457-probe2 silent TRUE pass was accepted")
        return 1
    if not planted["permanent_block_fails"]:
        print("FAILED:IMP-0457-probe2 permanent FALSE block was accepted")
        return 1
    if not planted["good_pr_only_valid"] or not planted["good_canary_valid"]:
        print("FAILED:IMP-0457-probe2 honest evaluations must validate")
        return 1
    if good["program_may_stop"] is True:
        print("FAILED:IMP-0457-probe2 required FALSEs must not allow stop")
        return 1

    if not ART.is_file():
        print("FAILED:IMP-0457-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    na_rows = [
        r
        for r in (doc.get("conditions") or [])
        if str(r.get("verdict") or "") == "NOT-APPLICABLE"
    ]
    if not na_rows:
        print("FAILED:IMP-0457-probe2 receipt has no N/A row")
        return 1
    for row in na_rows:
        if not str(row.get("owner_visible_justification") or "").strip():
            print("FAILED:IMP-0457-probe2 receipt N/A lacks justification")
            return 1
        if not str(row.get("owner_decision_id") or "").strip():
            print("FAILED:IMP-0457-probe2 receipt N/A lacks owner decision id")
            return 1
    receipt_errors = SP.validate_rows(
        list(doc.get("conditions") or []),
        release_mode=str(doc.get("binding_release_mode") or "PR-ONLY"),
    )
    if receipt_errors:
        print("FAILED:IMP-0457-probe2 receipt rows invalid", receipt_errors)
        return 1
    print(
        "SUCCESS:IMP-0457-probe2 unjustified N/A, silent pass, and "
        "permanent block all fail validation"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
