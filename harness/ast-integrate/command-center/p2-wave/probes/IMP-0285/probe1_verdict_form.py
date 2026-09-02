#!/usr/bin/env python3
"""Named probe 1 — unit: verdict form validation.

Valid DECISION and NO-DECISION forms must pass. A DECISION without a finding,
a NO-DECISION with a coerced finding, a judge seated as a juror, and an unknown
outcome kind must each fail with a named error code.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from load_jury import load_jury  # noqa: E402

jury = load_jury()


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0285-probe1 {msg}")
    return 1


def main() -> int:
    fixtures = jury.verdict_form_fixtures()
    valid_d = fixtures["valid_decision"]
    valid_h = fixtures["valid_hung"]
    err_d = jury.validate_verdict_form(valid_d)
    err_h = jury.validate_verdict_form(valid_h)
    if err_d:
        return fail(f"valid DECISION rejected {err_d}")
    if err_h:
        return fail(f"valid NO-DECISION rejected {err_h}")

    missing_kind = dict(valid_d)
    missing_kind["outcome_kind"] = "PASS"
    codes = {e["code"] for e in jury.validate_verdict_form(missing_kind)}
    if "outcome-kind" not in codes:
        return fail(f"PASS/FAIL kind not rejected codes={codes}")

    no_finding = dict(valid_d)
    no_finding["finding"] = None
    codes = {e["code"] for e in jury.validate_verdict_form(no_finding)}
    if "decision-finding" not in codes:
        return fail(f"DECISION without finding not rejected codes={codes}")

    coerced = dict(valid_h)
    coerced["finding"] = "CONVICT"
    codes = {e["code"] for e in jury.validate_verdict_form(coerced)}
    if "hung-finding" not in codes:
        return fail(f"NO-DECISION with finding not rejected codes={codes}")

    judge_votes = dict(valid_d)
    judge_votes["juror_ids"] = list(valid_d["juror_ids"]) + [valid_d["judge_id"]]
    codes = {e["code"] for e in jury.validate_verdict_form(judge_votes)}
    if "judge-as-juror" not in codes:
        return fail(f"judge-as-juror not rejected codes={codes}")

    empty_tally = dict(valid_d)
    empty_tally["ballot_tally"] = {}
    codes = {e["code"] for e in jury.validate_verdict_form(empty_tally)}
    if "tally" not in codes:
        return fail(f"empty tally not rejected codes={codes}")

    hung_no_reason = dict(valid_h)
    hung_no_reason["hung_reason"] = ""
    codes = {e["code"] for e in jury.validate_verdict_form(hung_no_reason)}
    if "hung-reason" not in codes:
        return fail(f"NO-DECISION without hung_reason not rejected codes={codes}")

    doc = {
        "pass": True,
        "probe": "probe1-verdict-form",
        "unit_id": "IMP-0285",
        "valid_decision_errors": err_d,
        "valid_hung_errors": err_h,
        "rejected": [
            "outcome-kind:PASS",
            "decision-finding:null",
            "hung-finding:CONVICT",
            "judge-as-juror",
            "empty-tally",
            "hung-reason-empty",
        ],
    }
    print(json.dumps(doc, sort_keys=True))
    print("SUCCESS:IMP-0285-probe1 verdict form validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
