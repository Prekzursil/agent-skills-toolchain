#!/usr/bin/env python3
"""Probe 2: missing sentinel must FAIL the predicate (wiring is live).

Negative control recorded verbatim: what the check does on the state it
is meant to reject (exit 0 + schema-valid file, sentinel stripped).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures_lib import (  # noqa: E402
    base_env,
    circular_reviewer,
    missing_sentinel,
    unread_consumer,
)
from predicate import NEGATIVE_CONTROL_VERBATIM, evaluate  # noqa: E402

ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0125-council-result-against-the-shared-12-condition-completion-.md"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0125-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("design note missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNL-0125" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent on the unit artifact")

    good = evaluate(base_env(), REPO)
    bad = evaluate(missing_sentinel(), REPO)
    circ = evaluate(circular_reviewer(), REPO)
    unread = evaluate(unread_consumer(), REPO)

    print("VERBATIM known-good " + json.dumps(
        {"complete": good["complete"], "unsatisfied": good["unsatisfied"], "exit_code": good["exit_code"]},
        sort_keys=True,
    ))
    print("VERBATIM missing-sentinel " + json.dumps(
        {"complete": bad["complete"], "unsatisfied": bad["unsatisfied"], "exit_code": bad["exit_code"]},
        sort_keys=True,
    ))
    print("VERBATIM circular-reviewer " + json.dumps(
        {"complete": circ["complete"], "unsatisfied": circ["unsatisfied"]},
        sort_keys=True,
    ))
    print("VERBATIM unread-consumer " + json.dumps(
        {"complete": unread["complete"], "unsatisfied": unread["unsatisfied"]},
        sort_keys=True,
    ))
    print("NEGATIVE_CONTROL_VERBATIM " + NEGATIVE_CONTROL_VERBATIM)

    if good["complete"] is not True:
        return fail(f"known-good not complete {good['unsatisfied']}")
    if good["exit_code"] != 0:
        return fail("known-good exit_code is not 0 (control would be vacuous)")
    if bad["complete"] is not False:
        return fail("missing-sentinel did not FAIL the predicate")
    if 5 not in bad["unsatisfied"]:
        return fail(f"missing-sentinel unsatisfied={bad['unsatisfied']} (C5 must fire)")
    if bad["exit_code"] != 0:
        return fail("missing-sentinel exit_code is not 0; would not prove anti-pattern 1")
    if 9 not in circ["unsatisfied"]:
        return fail("circular reviewer (seated participant) did not fail C9")
    if 12 not in unread["unsatisfied"]:
        return fail("consumer missing required fields did not fail C12")

    nc = doc.get("negative_control") or {}
    verbatim = str(nc.get("verbatim") or "")
    if NEGATIVE_CONTROL_VERBATIM not in verbatim and verbatim != NEGATIVE_CONTROL_VERBATIM:
        # require the artifact to record the same rejection
        if "condition 5 UNSATISFIED" not in verbatim:
            return fail("artifact negative_control.verbatim does not record C5 rejection")

    both = doc.get("both_states") or {}
    kg = both.get("known_good") or {}
    pb = both.get("planted_bad") or {}
    if kg.get("complete") is not True:
        return fail("both_states.known_good.complete is not true")
    if pb.get("complete") is not False:
        return fail("both_states.planted_bad.complete is not false")

    print("SILENT on known-good; FIRES on missing-sentinel (C5)")
    print("SUCCESS:CNL-0125-probe2 missing-sentinel wiring live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
