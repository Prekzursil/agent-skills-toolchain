#!/usr/bin/env python3
"""Probe 2: negative control — fabricated critique ids must FAIL citation check.

Both-states (single-signal-verification):
  * genuine critique-point ids -> check.ok True (silent on good)
  * fabricated id CP-FABRICATED-DOES-NOT-EXIST -> check.ok False AND issue_ruling refuses
  * empty citations -> check.ok False
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import fixture as F  # noqa: E402
from tools.council.topology.pcj import (  # noqa: E402
    PCJError,
    Ruling,
    check_citations,
    fabricated_citation_control,
    issue_ruling,
)

OUT = HERE / "probe2-fabricated-citations.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0283-probe2 {msg}")
    return 1


def main() -> int:
    _proposal, _critique, view = F.make_view()
    genuine = [p["point_id"] for p in view["points"]]
    if "CP-1" not in genuine:
        return fail("fixture lost CP-1")

    ctrl = fabricated_citation_control(
        view,
        genuine=genuine[:1],
        fabricated=F.FABRICATED_POINT_ID,
        judge_id=F.JUDGE_ID,
    )
    if not ctrl["silent_on_good_state"]:
        return fail("genuine citations did not pass (detector inert or inverted)")
    if not ctrl["fired_on_bad_state"]:
        return fail("fabricated citations were not refused")
    if ctrl["bad_ok"]:
        return fail("fabricated citation check returned ok=True")
    if F.FABRICATED_POINT_ID not in ctrl["unresolved"]:
        return fail(f"fabricated id not in unresolved {ctrl['unresolved']}")
    if ctrl["empty_ok"]:
        return fail("empty citations were accepted")
    if not ctrl["issue_ruling_refused_fabricated"]:
        return fail("issue_ruling accepted a fabricated critique id")

    # Direct both-states on check_citations itself (not just the helper).
    good = issue_ruling(
        view,
        ruling_id="probe2-good",
        judge_id=F.JUDGE_ID,
        verdict="reject",
        citations=genuine,
    )
    good_check = check_citations(good, view)
    bad = Ruling(
        ruling_id="probe2-bad",
        judge_id=F.JUDGE_ID,
        verdict="accept",
        citations=(F.FABRICATED_POINT_ID,),
        rationale="fabricated",
    )
    bad_check = check_citations(bad, view)
    empty = Ruling(
        ruling_id="probe2-empty",
        judge_id=F.JUDGE_ID,
        verdict="accept",
        citations=(),
        rationale="none",
    )
    empty_check = check_citations(empty, view)
    if not good_check.ok or bad_check.ok or empty_check.ok:
        return fail(
            f"direct check_citations both-states failed good={good_check.ok} "
            f"bad={bad_check.ok} empty={empty_check.ok}"
        )
    refused = False
    try:
        issue_ruling(
            view,
            ruling_id="probe2-refused",
            judge_id=F.JUDGE_ID,
            verdict="accept",
            citations=[F.FABRICATED_POINT_ID],
        )
    except PCJError:
        refused = True
    if not refused:
        return fail("issue_ruling did not raise on fabricated id")

    payload = {
        "probe": "probe2-fabricated-citations",
        "unit_id": F.UNIT,
        "pass": True,
        "negative_control": {
            "id": "NC-FABRICATED-CRITIQUE-IDS-FAIL",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "fabricated_id": F.FABRICATED_POINT_ID,
            "unresolved": list(bad_check.unresolved),
            "bad_reason": bad_check.reason,
            "empty_reason": empty_check.reason,
            "issue_ruling_refused_fabricated": True,
        },
        "genuine_point_ids": genuine,
        "good_ok": good_check.ok,
        "bad_ok": bad_check.ok,
        "empty_ok": empty_check.ok,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(
        f"good_ok={good_check.ok} bad_ok={bad_check.ok} empty_ok={empty_check.ok} "
        f"refused={refused} unresolved={list(bad_check.unresolved)}"
    )
    print("SUCCESS:IMP-0283-probe2 fabricated-critique-ids-fail both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
