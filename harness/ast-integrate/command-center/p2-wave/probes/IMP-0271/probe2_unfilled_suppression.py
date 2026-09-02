#!/usr/bin/env python3
"""Probe 2: suppress the unfilled report and the census check FAILS.

Both-states control, mechanically different from probe 1's five-mix
arithmetic: this probe starts from one unfillable run and tampers only
the unfilled_report field. The honest artifact must PASS census_check;
the suppressed copy must FAIL. A selector that never emitted the report
would fail the honest state. A check that ignored the report would
fail to go red on suppression.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import fixtures as F  # noqa: E402
from council.participants.select_stakeholder import (  # noqa: E402
    REASON_SUPPRESSED,
    census_check,
    select,
)

UNIT = "IMP-0271"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    pool = F.candidate_pool()
    mix = next(m for m in F.mixes() if m["id"] == "unfillable-regulator")
    honest = F.run_mix(select, pool, mix)
    if not honest["unfilled_report"]:
        return fail("honest run has empty unfilled_report")
    if not honest["under_represented"]:
        return fail("honest run did not flag under_represented")
    if honest["census"]["regulator"] != 1:
        return fail("honest run filled regulator silently")

    honest_check = census_check(honest)
    if not honest_check["ok"]:
        return fail(f"honest census_check failed: {honest_check}")

    suppressed = copy.deepcopy(honest)
    suppressed["unfilled_report"] = []
    suppressed["unfilled_report_emitted"] = False
    # Leave under_represented and census intact so the only mutation is
    # the missing report — the state the check is meant to reject.
    suppressed_check = census_check(suppressed)
    if suppressed_check["ok"]:
        return fail(
            "census_check stayed silent after unfilled_report was suppressed"
        )
    if suppressed_check["reason"] != REASON_SUPPRESSED:
        return fail(
            f"suppressed reason={suppressed_check['reason']!r} "
            f"expected={REASON_SUPPRESSED!r}"
        )

    omitted = copy.deepcopy(honest)
    omitted.pop("unfilled_report", None)
    omitted_check = census_check(omitted)
    if omitted_check["ok"] or omitted_check["reason"] != REASON_SUPPRESSED:
        return fail(f"omitted-key check did not fail suppressed: {omitted_check}")

    payload = {
        "probe": "probe2-unfilled-suppression",
        "unit_id": UNIT,
        "honest_ok": honest_check["ok"],
        "honest_reason": honest_check["reason"],
        "suppressed_ok": suppressed_check["ok"],
        "suppressed_reason": suppressed_check["reason"],
        "omitted_ok": omitted_check["ok"],
        "omitted_reason": omitted_check["reason"],
        "unfilled_classes": [
            r["stakeholder_class"] for r in honest["unfilled_report"]
        ],
        "regulator_seated": honest["census"]["regulator"],
        "regulator_requested": honest["requested_balance"]["regulator"],
        "both_states": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "honest_ok=True suppressed_ok=False reason=UNFILLED_REPORT_SUPPRESSED "
        "regulator_seated=1 requested=3"
    )
    print(
        "SUCCESS:IMP-0271-probe2 suppress unfilled report → census check FAILS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
