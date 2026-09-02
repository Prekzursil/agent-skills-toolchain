#!/usr/bin/env python3
"""Probe 2: offline re-evaluation of recorded inputs reproduces every verdict.

Catalog tests_required[1]: offline re-evaluation of recorded inputs
reproduces every iteration verdict.

The live state is discarded. Only predicate_inputs (expr + bindings the
evaluator actually read) are kept. Re-running evaluate_from_inputs must
match the recorded verdict. Mutating a binding must flip at least one
verdict so this is not a stored-bit echo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(REPO / "tools" / "agentrail"))

from agentrail.runner import (  # noqa: E402
    evaluate_from_inputs,
    execute_loop,
    loop_result_to_dict,
)
from scenario import INITIAL, converging_loop, never_loop  # noqa: E402

OUT = HERE / "probe2-offline-reeval.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0216-probe2 {msg}")
    return 1


def replay(result_dict: dict) -> list[dict]:
    rows = []
    for rec in result_dict["iterations"]:
        inputs = rec["predicate_inputs"]
        if "bindings" not in inputs:
            raise AssertionError(f"iteration {rec['index']} missing bindings")
        offline = evaluate_from_inputs(inputs)
        rows.append(
            {
                "index": rec["index"],
                "recorded": rec["predicate_verdict"],
                "offline": offline,
                "match": offline == rec["predicate_verdict"],
                "bindings": inputs["bindings"],
            }
        )
    return rows


def main() -> int:
    live_never = execute_loop(never_loop(), INITIAL)
    live_conv = execute_loop(converging_loop(), INITIAL)
    # Discard live objects. Persist only JSON — the auditor's view.
    never_doc = json.loads(json.dumps(loop_result_to_dict(live_never)))
    conv_doc = json.loads(json.dumps(loop_result_to_dict(live_conv)))
    del live_never, live_conv

    never_rows = replay(never_doc)
    conv_rows = replay(conv_doc)
    if not never_rows or not conv_rows:
        return fail("empty iteration records")
    if any(not r["match"] for r in never_rows + conv_rows):
        return fail("offline re-eval diverged from recorded verdict")
    if any(r["recorded"] for r in never_rows):
        return fail("never-converging JSON claimed a True verdict")
    if not conv_rows[-1]["recorded"]:
        return fail("converging JSON last verdict is False")
    if "n" not in conv_rows[-1]["bindings"]:
        return fail("converging last iteration recorded no n binding — unfalsifiable")

    # Negative control: mutate the binding that made the last verdict True.
    mutated = json.loads(json.dumps(conv_doc["iterations"][-1]["predicate_inputs"]))
    original_n = mutated["bindings"]["n"]
    mutated["bindings"]["n"] = 0
    flipped = evaluate_from_inputs(mutated)
    if flipped == conv_rows[-1]["recorded"]:
        return fail("mutating n did not change the offline verdict (echo detector)")
    if flipped is not False:
        return fail(f"mutated n=0 still evaluated True (n was {original_n})")

    # A record with no inputs at all must be refused, not silently True/False.
    try:
        evaluate_from_inputs({"expr": {"op": "gte", "path": "n", "value": 3}})
        return fail("missing bindings was accepted")
    except Exception as exc:
        missing_bindings_refused = "loop-inputs-missing-bindings" in str(exc)

    if not missing_bindings_refused:
        return fail("missing bindings did not raise loop-inputs-missing-bindings")

    doc = {
        "pass": True,
        "probe": "probe2-offline-reeval",
        "unit_id": "IMP-0216",
        "never_matches": len(never_rows),
        "converging_matches": len(conv_rows),
        "all_match": True,
        "mutation_flipped": True,
        "missing_bindings_refused": True,
        "never_rows": never_rows,
        "converging_rows": conv_rows,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"never_matches={len(never_rows)} converging_matches={len(conv_rows)} "
        f"mutation_flipped=True missing_bindings_refused=True"
    )
    print("SUCCESS:IMP-0216-probe2 offline re-eval reproduces every iteration verdict")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
