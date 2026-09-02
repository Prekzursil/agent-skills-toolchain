"""IMP-0216 both-states Loop fixtures.

Twin loops share the same body (increment `n` by 1) and the same bound.
The never-converging twin has `op=never`; the converging twin stops when
`n >= 3`. If the bound is not enforced, the never twin would not stop at 8.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(REPO / "tools" / "agentrail"))

from agentrail.runner import Loop  # noqa: E402

BODY = ({"op": "incr", "path": "n", "by": 1},)
BOUND = 8
CONVERGE_AT = 3
INITIAL = {"n": 0}


def never_loop() -> Loop:
    return Loop(
        id="imp-0216-never",
        body=BODY,
        convergence_expr={"op": "never"},
        max_iterations=BOUND,
        on_bound_reached="abort",
    )


def converging_loop() -> Loop:
    return Loop(
        id="imp-0216-converge",
        body=BODY,
        convergence_expr={"op": "gte", "path": "n", "value": CONVERGE_AT},
        max_iterations=BOUND,
        on_bound_reached="abort",
    )


def fail_on_bound_loop() -> Loop:
    return Loop(
        id="imp-0216-fail-bound",
        body=BODY,
        convergence_expr={"op": "never"},
        max_iterations=BOUND,
        on_bound_reached="fail",
    )
