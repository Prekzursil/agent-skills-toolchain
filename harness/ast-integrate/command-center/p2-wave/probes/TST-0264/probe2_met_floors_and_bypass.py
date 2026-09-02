#!/usr/bin/env python3
"""Probe 2: floors-met + true stop terminates immediately; min_rounds=0 rejected.

Also the inverse control: floors met + expression false must NOT stop via the
expression (the floor is a precondition, not a substitute stop rule). A
max_rounds ceiling fires on the never-met floor so the gate cannot hang.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import scenario as S  # noqa: E402
from tools.council.simulate import run_council, validate_spec  # noqa: E402
from tools.council.stopping.minimum import (  # noqa: E402
    BYPASS_CODES,
    FLOOR_MIN_ROUNDS,
    REASON_CEILING,
    REASON_EXPRESSION_FALSE,
    REASON_STOP,
    SpecValidationError,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0264-probe2 {msg}")
    return 1


def main() -> int:
    healthy = run_council(S.spec(S.HEALTHY_SPEC), S.productive_cast(), apply_floors=True)
    again = run_council(S.spec(S.HEALTHY_SPEC), S.productive_cast(), apply_floors=True)
    if healthy["transcript_sha256"] != again["transcript_sha256"]:
        return fail("same spec+cast produced different transcript hashes")

    if len(healthy["stop_evals"]) < 2:
        return fail(f"expected two stop-evals, got {len(healthy['stop_evals'])}")
    r1, r2 = healthy["stop_evals"][0], healthy["stop_evals"][1]
    if int(r1["round"]) != 1 or r1["decision"] != "continue":
        return fail(f"round 1 should continue on min_rounds floor: {r1}")
    if r1.get("stop_expression_true") is not True:
        return fail("round 1 stop expression was not TRUE")
    if FLOOR_MIN_ROUNDS not in (r1.get("unmet_floors") or []):
        return fail(f"round 1 did not name min_rounds as unmet: {r1.get('unmet_floors')}")
    if r1.get("named_floor") != FLOOR_MIN_ROUNDS:
        return fail(f"round 1 named_floor={r1.get('named_floor')!r}")
    if int(r2["round"]) != 2 or r2["decision"] != "stop":
        return fail(f"round 2 should stop immediately once floors met: {r2}")
    if r2.get("reason") != REASON_STOP:
        return fail(f"round 2 reason {r2.get('reason')!r} is not {REASON_STOP}")
    if r2.get("floors_met") is not True:
        return fail("round 2 floors_met is not True")
    if int(healthy["rounds_completed"]) != 2:
        return fail(f"over-blocked: extra rounds after floors met ({healthy['rounds_completed']})")
    if len(healthy["stop_evals"]) != 2:
        return fail("run continued past the round floors were met")

    false_expr = run_council(S.spec(S.FALSE_STOP_SPEC), S.productive_cast(), apply_floors=True)
    r2_false = next((e for e in false_expr["stop_evals"] if int(e["round"]) == 2), None)
    if r2_false is None:
        return fail("false-expression run has no round-2 stop-eval")
    if r2_false.get("stop_expression_true") is not False:
        return fail("false expression evaluated true")
    if r2_false.get("decision") == "stop" and r2_false.get("reason") == REASON_STOP:
        return fail("floors-met substituted for a false stop expression")
    if r2_false.get("reason") not in {REASON_EXPRESSION_FALSE, REASON_CEILING}:
        return fail(f"false-expression round 2 reason unexpected: {r2_false.get('reason')}")

    bypass_code = None
    bypass_msg = None
    try:
        validate_spec(S.spec(S.BYPASS_SPEC))
        return fail("min_rounds=0 was accepted at validation time")
    except SpecValidationError as exc:
        bypass_code = exc.code
        bypass_msg = exc.message
    expected = BYPASS_CODES[FLOOR_MIN_ROUNDS]
    if bypass_code != expected:
        return fail(f"bypass code {bypass_code!r} is not {expected}")
    try:
        run_council(S.spec(S.BYPASS_SPEC), S.silent_cast())
        return fail("min_rounds=0 reached runtime (must fail at validation)")
    except SpecValidationError as exc:
        if exc.code != expected:
            return fail(f"runtime validate code {exc.code!r} is not {expected}")

    ceiling = run_council(S.spec(S.PREMATURE_SPEC), S.silent_cast(), apply_floors=True)
    if ceiling.get("terminated_by") != REASON_CEILING:
        return fail(f"never-met floor did not hit max-rounds ceiling: {ceiling.get('terminated_by')}")
    if int(ceiling["rounds_completed"]) != int(S.PREMATURE_SPEC["max_rounds"]):
        return fail("ceiling fired on the wrong round")

    out = {
        "probe": "probe2-met-floors-and-bypass",
        "unit_id": "TST-0264",
        "pass": True,
        "healthy_stopped_round": healthy["rounds_completed"],
        "healthy_reason": r2["reason"],
        "round1_named_floor": r1["named_floor"],
        "transcript_sha256": healthy["transcript_sha256"],
        "determinism": True,
        "false_expression_did_not_stop_via_floors": True,
        "false_expression_round2_reason": r2_false["reason"],
        "min_rounds_zero_rejected": True,
        "bypass_code": bypass_code,
        "bypass_message": bypass_msg,
        "ceiling_reason": ceiling["terminated_by"],
        "ceiling_rounds": ceiling["rounds_completed"],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"stopped_round=2 no_overblock=True bypass={bypass_code} "
        f"ceiling={ceiling['terminated_by']}"
    )
    print("SUCCESS:TST-0264-probe2 floors-met stops; min_rounds=0 rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
