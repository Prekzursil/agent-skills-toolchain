#!/usr/bin/env python3
"""Probe 1: permissive stop TRUE in round 1 with zero independent briefs.

The run must CONTINUE and the transcript must name the unmet floor
`independent_opening_positions`. Both-states: disable the floor gate and the
same fixture stops in round 1 — proving the detector is not a tautology.
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
from tools.council.simulate import run_council  # noqa: E402
from tools.council.stopping.expr import evaluate  # noqa: E402
from tools.council.stopping.minimum import (  # noqa: E402
    FLOOR_INDEPENDENT_OPENING_POSITIONS,
    REASON_FLOOR_BLOCKS,
    REASON_GATE_DISABLED,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0264-probe1 {msg}")
    return 1


def main() -> int:
    if evaluate(S.PERMISSIVE_STOP, {}) is not True:
        return fail("permissive expression `true` did not evaluate True")

    floored = run_council(S.spec(S.PREMATURE_SPEC), S.silent_cast(), apply_floors=True)
    ungated = run_council(S.spec(S.PREMATURE_SPEC), S.silent_cast(), apply_floors=False)

    if not floored["stop_evals"]:
        return fail("floored run produced no stop-eval records")
    first = floored["stop_evals"][0]
    if int(first.get("round") or 0) != 1:
        return fail(f"first stop-eval is not round 1: {first}")
    if first.get("stop_expression_true") is not True:
        return fail("stop expression was not TRUE in round 1")
    if first.get("decision") != "continue":
        return fail(f"floored run stopped in round 1: {first}")
    if first.get("reason") != REASON_FLOOR_BLOCKS:
        return fail(f"round-1 continue reason is not floor-blocks: {first.get('reason')}")
    unmet = list(first.get("unmet_floors") or [])
    if FLOOR_INDEPENDENT_OPENING_POSITIONS not in unmet:
        return fail(f"independent_opening_positions not in unmet_floors={unmet}")
    named = first.get("named_floor")
    if named != FLOOR_INDEPENDENT_OPENING_POSITIONS:
        return fail(f"named_floor={named!r} is not independent_opening_positions")
    msg = str(first.get("floor_block_message") or "")
    if FLOOR_INDEPENDENT_OPENING_POSITIONS not in msg:
        return fail(f"floor_block_message does not name the floor: {msg!r}")
    briefs_n = first.get("measured", {}).get("independent_briefs")
    if briefs_n != 0:
        return fail(f"round 1 independent_briefs is not zero: {briefs_n!r}")
    if floored["terminated_by"] == "expression-true-floors-met":
        return fail("floored silent run terminated via the stop expression")

    if ungated["stop_evals"][0].get("decision") != "stop":
        return fail("negative control (gate disabled) did not stop in round 1")
    if ungated["stop_evals"][0].get("reason") != REASON_GATE_DISABLED:
        return fail(
            f"ungated stop reason {ungated['stop_evals'][0].get('reason')!r} "
            f"is not {REASON_GATE_DISABLED}"
        )
    if int(ungated.get("rounds_completed") or 0) != 1:
        return fail("ungated fixture did not stop at round 1")

    blob = json.dumps(floored["transcript"])
    if FLOOR_INDEPENDENT_OPENING_POSITIONS not in blob:
        return fail("transcript JSON does not contain the named floor id")

    out = {
        "probe": "probe1-premature-stop-floored",
        "unit_id": "TST-0264",
        "pass": True,
        "both_states": True,
        "round": 1,
        "stop_expression": S.PERMISSIVE_STOP,
        "stop_expression_true": True,
        "floored_decision": first["decision"],
        "floored_reason": first["reason"],
        "named_floor": named,
        "unmet_floors": unmet,
        "floor_block_message": msg,
        "independent_briefs": first["measured"]["independent_briefs"],
        "ungated_stopped_round": ungated["rounds_completed"],
        "ungated_reason": ungated["stop_evals"][0]["reason"],
        "floored_transcript_sha256": floored["transcript_sha256"],
        "ungated_transcript_sha256": ungated["transcript_sha256"],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"stop_true=True decision=continue named_floor={named} "
        f"ungated_stop_round={ungated['rounds_completed']}"
    )
    print("SUCCESS:TST-0264-probe1 premature stop floored; ungated control stops")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
