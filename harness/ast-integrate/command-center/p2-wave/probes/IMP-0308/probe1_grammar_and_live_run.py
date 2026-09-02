#!/usr/bin/env python3
"""IMP-0308 probe 1: parser grammar (precedence, negation) and live 6-expression run.

Prints every bound metric on every round. An AND under partial evidence must
stay false (not silently become OR).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.stopping.expr import (  # noqa: E402
    SPEC_EXPRESSIONS,
    bind,
    evaluate,
    live_run,
    parse,
    referenced_metrics,
    spec_producers,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0308-probe1 {msg}")
    return 1


def main() -> int:
    # Precedence: AND tighter than OR.
    # false AND true OR true = (false AND true) OR true = true
    # if OR were tighter: false AND (true OR true) = false
    snap = {"f": False, "t": True}
    prod = {"f": lambda r: False, "t": lambda r: True}
    got = bind("f AND t OR t", prod).evaluate(snap)
    print(f"precedence AND-vs-OR: {got} expected=True")
    if got is not True:
        return fail("AND did not bind tighter than OR")

    # NOT tighter than AND. a=0,b=0:
    # NOT a >= 1 AND b >= 1  => (NOT false) AND false = false
    # NOT (a >= 1 AND b >= 1) => NOT false = true
    snap2 = {"a": 0, "b": 0}
    prod2 = {"a": lambda r: 0, "b": lambda r: 0}
    got2 = bind("NOT a >= 1 AND b >= 1", prod2).evaluate(snap2)
    print(f"precedence NOT-vs-AND: {got2} expected=False")
    if got2 is not False:
        return fail("NOT did not bind tighter than AND")

    nested = bind("NOT (a >= 1 AND b >= 1)", prod2).evaluate(snap2)
    print(f"negation grouped: {nested} expected=True")
    if nested is not True:
        return fail("grouped NOT failed")

    # Partial evidence must not turn AND into OR.
    and_src = "unique_ideas >= 100 AND completeness_score >= 0.90"
    partial = {"unique_ideas": 100, "completeness_score": 0.0}
    and_val = evaluate(and_src, partial)
    print(f"AND partial-evidence unique_ideas=100 completeness=0.0 -> {and_val}")
    if and_val is not False:
        return fail("AND behaved as OR under partial evidence")

    any_n = bind("ANY(a >= 1, b >= 1)", prod2)
    all_n = bind("ALL(a >= 1, b >= 1)", {"a": lambda r: 0, "b": lambda r: 1})
    if any_n.evaluate({"a": 0, "b": 1}) is not True:
        return fail("ANY failed")
    if all_n.evaluate({"a": 0, "b": 1}) is not False:
        return fail("ALL failed")
    wsrc = "WEIGHTED(0.6 * consensus + 0.4 * completeness_score) >= 0.90"
    w = bind(wsrc, spec_producers())
    w0, _ = w.evaluate_round(1)
    w12, wsnap = w.evaluate_round(12)
    print(f"WEIGHTED r1={w0} r12={w12} metrics={wsnap}")
    if w0 is not False or w12 is not True:
        return fail("WEIGHTED did not change across the live run")

    parsed = []
    for eid, line, src in SPEC_EXPRESSIONS:
        node = parse(src)
        mets = sorted(referenced_metrics(node))
        parsed.append({"id": eid, "spec_line": line, "source": src, "metrics": mets})
        print(f"parsed {eid} line={line} metrics={mets} src={src}")
    if len(parsed) != 6:
        return fail("expected six spec expressions")

    run = live_run()
    for row in run["per_round"]:
        r = row["round"]
        for expr in row["expressions"]:
            mets = expr["bound_metrics"]
            print(
                f"round={r} {expr['id']} value={expr['value']} bound={json.dumps(mets, sort_keys=True)}"
            )

    changed = run["changed_during_run"]
    print("changed_during_run", json.dumps(changed, sort_keys=True))
    missing_flip = [k for k, v in changed.items() if not v]
    if missing_flip:
        return fail(f"expression value did not change during run: {missing_flip}")

    if not all(run["final"].values()):
        return fail(f"expected all six true by round 12, got {run['final']}")

    print("SUCCESS:IMP-0308-probe1 grammar precedence negation and live six-expression run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
