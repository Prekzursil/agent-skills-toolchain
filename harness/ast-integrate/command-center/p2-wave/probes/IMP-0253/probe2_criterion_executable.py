#!/usr/bin/env python3
"""Probe 2: resolution criterion executes against a synthetic future state.

A holding state resolves TRUE, a missing state resolves FALSE, a too-early
state is TOO_EARLY. Prose is not executed. Nested and flat observable
lookups must agree. Receipt must record the live numbers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center"))

import fixtures as F  # noqa: E402
from analysis.forecast_gate import (  # noqa: E402
    OBSERVABLE_ABSENT,
    REJECT_NOT_ADMITTED,
    RESOLVED_FALSE,
    RESOLVED_TRUE,
    TOO_EARLY,
    SyntheticState,
    resolve,
)

ART = REPO / "command-center/receipts/IMP-0253.json"
UNIT = "IMP-0253"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    hold = resolve(F.RESOLVABLE, F.HOLD)
    miss = resolve(F.RESOLVABLE, F.MISS)
    early = resolve(F.RESOLVABLE, F.EARLY)
    flat = resolve(F.RESOLVABLE, F.HOLD_FLAT)
    prose = resolve(F.UNRESOLVABLE_PROSE, F.HOLD)
    nodate = resolve(F.UNRESOLVABLE_NO_DATE, F.HOLD)
    absent = resolve(
        F.RESOLVABLE,
        SyntheticState(as_of="2027-03-01", observables={"other.metric": 1}),
    )

    print(
        json.dumps(
            {
                "hold": hold.to_dict(),
                "miss": miss.to_dict(),
                "early": early.to_dict(),
                "flat": flat.to_dict(),
                "prose": prose.to_dict(),
                "nodate": nodate.to_dict(),
                "absent": absent.to_dict(),
            },
            sort_keys=True,
        )
    )

    if not hold.resolved or hold.reason != RESOLVED_TRUE or hold.value is not True:
        return fail(f"hold {hold.to_dict()}")
    if hold.matches_prediction is not True:
        return fail("hold did not match predicted=True")
    if hold.observed != 150:
        return fail(f"hold observed={hold.observed} (must be looked up, not asserted)")
    if hold.prose_executed:
        return fail("hold executed prose")

    if not miss.resolved or miss.reason != RESOLVED_FALSE or miss.value is not False:
        return fail(f"miss {miss.to_dict()}")
    if miss.matches_prediction is not False:
        return fail("miss unexpectedly matched prediction")
    if miss.observed != 400:
        return fail(f"miss observed={miss.observed}")

    if early.resolved or early.reason != TOO_EARLY:
        return fail(f"early {early.to_dict()}")
    if early.value is not None:
        return fail("too-early produced a boolean (would fake a score)")

    if flat.reason != hold.reason or flat.value != hold.value:
        return fail("flat observable lookup disagreed with nested")

    if prose.resolved or prose.reason != REJECT_NOT_ADMITTED:
        return fail(f"prose executed or wrong reason {prose.to_dict()}")
    if prose.prose_executed:
        return fail("prose_executed leaked true")
    if nodate.resolved or nodate.reason != REJECT_NOT_ADMITTED:
        return fail(f"no-date resolve {nodate.to_dict()}")
    if absent.resolved or absent.reason != OBSERVABLE_ABSENT:
        return fail(f"absent observable {absent.to_dict()}")

    # A always-true resolver would fail the miss arm; an always-false
    # resolver would fail the hold arm. Both arms ran above.

    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0253" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    gate = doc.get("forecast_gate") or {}
    rec_hold = gate.get("resolve_hold") or {}
    rec_miss = gate.get("resolve_miss") or {}
    rec_early = gate.get("resolve_early") or {}
    if rec_hold.get("reason") != RESOLVED_TRUE or rec_hold.get("value") is not True:
        return fail("receipt resolve_hold drift")
    if rec_miss.get("reason") != RESOLVED_FALSE or rec_miss.get("value") is not False:
        return fail("receipt resolve_miss drift")
    if rec_early.get("reason") != TOO_EARLY:
        return fail("receipt resolve_early drift")
    if rec_hold.get("observed") != 150 or rec_miss.get("observed") != 400:
        return fail("receipt observed values were not the live lookups")

    print(
        "hold=RESOLVED_TRUE miss=RESOLVED_FALSE early=TOO_EARLY "
        "prose_not_executed=True"
    )
    print(
        f"SUCCESS:{UNIT}-probe2 criterion executed against synthetic state; "
        "prose not executed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
