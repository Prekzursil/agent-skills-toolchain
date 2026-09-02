#!/usr/bin/env python3
"""Probe 1: every dial's exhaustion fixture produces the declared behaviour.

Signal 1: evaluate().reason (and markers) on the planted fixture.
Signal 2: try_consume() / stopping_set size — a different field than reason.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import semantics as S  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0008-budget-block-12-dials-and-the-exhaustion-semantics.md"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0008-probe1 {msg}")
    return 1


def main() -> int:
    if len(S.DIAL_IDS) != 12:
        return fail(f"dial_count={len(S.DIAL_IDS)} want=12")
    rows = S.run_all_declared()
    if set(rows) != set(S.DIAL_IDS):
        return fail(f"row_ids={sorted(rows)} want={list(S.DIAL_IDS)}")

    mismatches = [d for d, r in rows.items() if not r["match"]]
    if mismatches:
        print(json.dumps({d: rows[d] for d in mismatches}, indent=2)[:2000])
        return fail(f"declared_reason_mismatch {mismatches}")

    for dial in ("effort", "time", "tokens", "turns"):
        st = S.fixture_for(dial)
        v = S.evaluate(st)
        if v.reason != "BUDGET_EXHAUSTED" or not v.terminal:
            return fail(f"{dial} reason={v.reason} terminal={v.terminal}")
        if v.agreement is not True:
            return fail(f"{dial} bait agreement missing (fixture broken)")
        if len(v.stopping_set) != 3:
            return fail(f"{dial} roster_shrunk declared {v.stopping_set}")
        spent = S.try_consume(st, dial)
        if spent["accepted"] is not False or spent["reason"] != "BUDGET_EXHAUSTED":
            return fail(f"{dial} extra consume {spent}")

    for dial in ("tool_calls", "sources", "experiments"):
        st = S.fixture_for(dial)
        v = S.evaluate(st)
        if v.reason != "CONSENSUS":
            return fail(f"{dial} reason={v.reason}")
        if f"DEGRADED:{dial}" not in v.markers:
            return fail(f"{dial} missing DEGRADED marker {v.markers}")
        if "COVERAGE_INCOMPLETE" not in v.markers:
            return fail(f"{dial} missing COVERAGE_INCOMPLETE {v.markers}")
        spent = S.try_consume(st, dial)
        if spent["accepted"] is not False or spent["reason"] != f"DEGRADED:{dial}":
            return fail(f"{dial} extra consume {spent}")

    for dial in ("speaking_quotas", "maximum_inactivity"):
        st = S.fixture_for(dial)
        v = S.evaluate(st)
        if v.reason != "CONTINUE":
            return fail(f"{dial} reason={v.reason}")
        if len(v.stopping_set) != 3 or len(st.seats) != 3:
            return fail(f"{dial} stopping_set={v.stopping_set}")
        if dial == "speaking_quotas":
            spent = S.try_consume(st, "speaking_quotas")
            if spent["accepted"] is not False:
                return fail(f"{dial} muted seat still spent {spent}")

    gate = S.evaluate(S.fixture_for("minimum_engagement"))
    if gate.reason != "ENGAGEMENT_UNMET":
        return fail(f"minimum_engagement reason={gate.reason}")
    if len(gate.stopping_set) != 3:
        return fail(f"minimum_engagement shrunk {gate.stopping_set}")
    mid = S.evaluate(S.midrun_engagement_unmet())
    if mid.reason != "CONTINUE" or mid.terminal:
        return fail(f"midrun_engagement reason={mid.reason} terminal={mid.terminal}")

    reb = S.evaluate(S.fixture_for("rebuttal_depth"))
    if reb.reason != "CONTINUE" or "OBLIGATION_OPEN" not in reb.markers:
        return fail(f"rebuttal_depth {reb.as_dict()}")

    esc = S.evaluate(S.fixture_for("escalation"))
    if esc.reason != "ESCALATION_EXHAUSTED":
        return fail(f"escalation reason={esc.reason}")

    if ART.is_file() and ART.stat().st_size > 0:
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("unit_id") != "CNL-0008":
            return fail(f"artifact unit_id={doc.get('unit_id')}")
        if "SUCCESS:CNL-0008" not in json.dumps(doc):
            return fail("artifact sentinel absent")
        dials = doc.get("dials") or []
        if len(dials) != 12:
            return fail(f"artifact dials={len(dials)}")
        by = {d["id"]: d for d in dials}
        for dial, row in rows.items():
            got = by.get(dial) or {}
            if got.get("exhaustion") != row["exhaustion"]:
                return fail(f"artifact {dial} exhaustion {got.get('exhaustion')}")
            if got.get("declared_reason_on_fixture") != row["want_reason"]:
                return fail(f"artifact {dial} reason {got.get('declared_reason_on_fixture')}")

    print(json.dumps({"declared": {d: rows[d]["reason"] for d in S.DIAL_IDS}}, sort_keys=True))
    print(
        "hard_stop_refused extra spend; degrade_refused extra capability; "
        "roster_frozen=3; gate_midrun=CONTINUE; gate_terminal=ENGAGEMENT_UNMET"
    )
    print("SUCCESS:CNL-0008-probe1 exhaustion fixtures for all 12 dials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
