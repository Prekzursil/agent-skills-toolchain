#!/usr/bin/env python3
"""Probe 2: never-true rejected at compile; already-true at t0 flagged degenerate.

Both-states: unique_ideas>=100 is false at t0 and true after unique_ideas=100.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import algebra as A  # noqa: E402

ART = REPO / (
    "command-center/foundry/"
    "WFA-0156-typed-stopping-rule-algebra-with-executable-evaluati.json"
)


def main() -> int:
    if not ART.is_file():
        print("FAILED:WFA-0156-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0156-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:WFA-0156" not in text:
        print("FAILED:WFA-0156-probe2 sentinel absent")
        return 1

    live = A.both_states_controls()
    recorded = doc.get("both_states") or {}

    never = live["never_true"]
    already = live["already_true_at_t0"]
    becomes = live["becomes_true"]
    print(
        f"never source={never['source']} result={never['compile_result']} "
        f"rejected={never['rejected_at_compile']} reason={never['reject_reason']}"
    )
    print(
        f"t0-true source={already['source']} result={already['compile_result']} "
        f"degen={already['degenerate_immediate_stop']} eval_t0={already['eval_t0']}"
    )
    print(
        f"live source={becomes['source']} t0={becomes['eval_t0']} "
        f"later={becomes['eval_later_unique_ideas_100']} "
        f"degen={becomes['degenerate_immediate_stop']}"
    )

    if not never["rejected_at_compile"] or never["compile_result"] != "COMPILE-REJECT":
        print("FAILED:WFA-0156-probe2 never-true not compile-rejected")
        return 1
    if already["compile_result"] != "EVALUABLE" or not already["degenerate_immediate_stop"]:
        print("FAILED:WFA-0156-probe2 t0-true not flagged degenerate")
        return 1
    if already["eval_t0"] is not True:
        print("FAILED:WFA-0156-probe2 t0-true eval is not True")
        return 1
    if becomes["eval_t0"] is not False:
        print("FAILED:WFA-0156-probe2 live predicate true at t0")
        return 1
    if becomes["eval_later_unique_ideas_100"] is not True:
        print("FAILED:WFA-0156-probe2 live predicate not true later")
        return 1
    if becomes["degenerate_immediate_stop"]:
        print("FAILED:WFA-0156-probe2 live predicate wrongly degenerate")
        return 1

    rec_never = recorded.get("never_true") or {}
    rec_already = recorded.get("already_true_at_t0") or {}
    rec_live = recorded.get("becomes_true") or {}
    if rec_never.get("rejected_at_compile") is not True:
        print("FAILED:WFA-0156-probe2 artifact never_true drift")
        return 1
    if rec_already.get("degenerate_immediate_stop") is not True:
        print("FAILED:WFA-0156-probe2 artifact already_true drift")
        return 1
    if rec_live.get("eval_t0") is not False or rec_live.get("eval_later_unique_ideas_100") is not True:
        print("FAILED:WFA-0156-probe2 artifact becomes_true drift")
        return 1

    print(
        "NEGATIVE-CONTROL: ALL(done==true, NOT(done==true)) is rejected at "
        f"compile ({never['reject_reason']}); it is not evaluated as a "
        "permanent false that could later flip. POSITIVE-CONTROL: rounds>=0 "
        "is already true at t0 and is flagged degenerate_immediate_stop. "
        "BOTH-STATES: unique_ideas>=100 is false at t0 and true at 100."
    )
    out = {
        "probe": "probe2-degenerate",
        "unit_id": "WFA-0156",
        "never_true_rejected": True,
        "t0_true_degenerate": True,
        "becomes_true_flips": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:WFA-0156-probe2 never-true rejected; t0-true flagged degenerate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
