#!/usr/bin/env python3
"""Named probe 2 — hung jury is NO-DECISION; unsupported verdict fails support check.

Integration: a 3–2 split under unanimity must yield NO-DECISION, not the
plurality CONVICT that coerce_plurality_finding would pick.

Negative control: plant a finding no juror reasoned toward; check_verdict_support
must FAIL and list it in unsupported.
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
    print(f"FAILED:IMP-0285-probe2 {msg}")
    return 1


def main() -> int:
    hung = jury.run_jury(jury.hung_jury_fixture())
    v = hung.verdict
    coerced = jury.coerce_plurality_finding(v.ballot_tally)
    if v.outcome_kind != jury.OUTCOME_NO_DECISION:
        return fail(f"hung outcome_kind={v.outcome_kind!r} want NO-DECISION")
    if v.finding is not None:
        return fail(f"hung finding coerced to {v.finding!r}")
    if v.hung_reason != "threshold-not-met":
        return fail(f"hung_reason={v.hung_reason!r}")
    if coerced != "CONVICT":
        return fail(f"plurality control expected CONVICT got {coerced!r}")
    if v.finding == coerced:
        return fail("run_jury used plurality coercion")
    if v.ballot_tally.get("CONVICT") != 3 or v.ballot_tally.get("ACQUIT") != 2:
        return fail(f"unexpected tally {v.ballot_tally}")
    form_errs = jury.validate_verdict_form(v)
    if form_errs:
        return fail(f"hung form invalid {form_errs}")
    if not hung.support.ok:
        return fail(f"lawful hung marked unsupported {hung.support.to_dict()}")
    rumor = [row for row in hung.excluded if row["exhibit_id"] == "EX-RUMOR-9"]
    if not rumor:
        return fail("below-tier rumor was admitted")
    if rumor[0].get("claimed_tier") != jury.TIER_EXECUTABLE:
        return fail("claimed_tier not preserved on the exclusion record")
    if "EX-RUMOR-9" in hung.admitted:
        return fail("rumor id in admitted")
    judge_turns = [t for t in hung.turns if t["participant_id"] == "JUDGE-1"]
    if not judge_turns or judge_turns[0]["kind"] != "admissibility":
        return fail("judge did not record an admissibility turn")
    if any(t["kind"] == "juror-reasoning" and t["participant_id"] == "JUDGE-1" for t in hung.turns):
        return fail("judge cast a juror-reasoning turn")

    tied = jury.run_jury(jury.tie_hung_fixture())
    if tied.verdict.outcome_kind != jury.OUTCOME_NO_DECISION or tied.verdict.finding is not None:
        return fail(
            f"tie coerced outcome={tied.verdict.outcome_kind} finding={tied.verdict.finding}"
        )

    uni = jury.run_jury(jury.unanimous_supported_fixture())
    if uni.verdict.outcome_kind != jury.OUTCOME_DECISION or uni.verdict.finding != "CONVICT":
        return fail(
            f"unanimous outcome={uni.verdict.outcome_kind} finding={uni.verdict.finding}"
        )
    if not uni.support.ok or uni.support.unsupported:
        return fail(f"supported verdict failed check {uni.support.to_dict()}")
    if not uni.support.supported_by.get("CONVICT"):
        return fail("supported_by missing CONVICT jurors")

    planted = jury.plant_unsupported_verdict(uni, "PLANTED-WRONG")
    planted_report = jury.check_verdict_support(planted, uni.juror_records)
    if planted_report.ok:
        return fail("planted unsupported verdict passed the support check")
    findings = [u.finding for u in planted_report.unsupported]
    if "PLANTED-WRONG" not in findings:
        return fail(f"unsupported list missed plant {planted_report.to_dict()}")

    empty = jury.run_jury(jury.empty_reasoning_fixture())
    empty_report = jury.check_verdict_support(empty.verdict, empty.juror_records)
    if empty_report.ok or not empty_report.unsupported:
        return fail("empty-reasoning verdict did not fail support check")

    doc = {
        "pass": True,
        "probe": "probe2-hung-and-support",
        "unit_id": "IMP-0285",
        "hung": {
            "outcome_kind": v.outcome_kind,
            "finding": v.finding,
            "hung_reason": v.hung_reason,
            "ballot_tally": v.ballot_tally,
            "plurality_would_have_been": coerced,
            "excluded_rumor": rumor[0],
        },
        "tie_outcome_kind": tied.verdict.outcome_kind,
        "unanimous_support_ok": uni.support.ok,
        "unsupported_planted": planted_report.to_dict()["unsupported"],
        "empty_reasoning_unsupported": empty_report.to_dict()["unsupported"],
    }
    print(json.dumps(doc, sort_keys=True))
    print("SUCCESS:IMP-0285-probe2 hung jury NO-DECISION and unsupported-verdict FAIL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
