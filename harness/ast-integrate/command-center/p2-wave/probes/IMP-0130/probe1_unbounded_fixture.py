#!/usr/bin/env python3
"""Probe 1: unbounded Loop fixture fails validation; bounded twins pass.

Signal (1) of IMP-0130: the unbounded-Loop fixture yields the new violation
id ``loop-unbounded``. Both-states control: bounded twins (max_iterations,
convergence_expr, or both) produce zero violations. Construction of an
unbounded Loop value is refused by the type (ValueError loop-unbounded).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.spec import Loop  # noqa: E402
from agentspec.validate import (  # noqa: E402
    VIOLATION_LOOP_UNBOUNDED,
    validate_workflow,
    violation_ids,
)

FIXTURES = HERE / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def main() -> int:
    unbounded = _load("unbounded-loop.json")
    bounded = _load("bounded-loop.json")
    conv_only = _load("bounded-convergence-only.json")
    max_only = _load("bounded-max-only.json")

    u_viol = validate_workflow(unbounded)
    b_viol = validate_workflow(bounded)
    c_viol = validate_workflow(conv_only)
    m_viol = validate_workflow(max_only)
    u_ids = violation_ids(u_viol)

    type_refused = False
    try:
        Loop(
            id="council-loop",
            body=("deliberate",),
            convergence_expr=None,
            max_iterations=None,
            on_bound_reached="abort",
        )
    except ValueError as exc:
        type_refused = str(exc) == VIOLATION_LOOP_UNBOUNDED

    constructed = Loop(
        id="council-loop",
        body=("deliberate",),
        convergence_expr="information_gain < 0.01",
        max_iterations=4,
        on_bound_reached="abort",
    )
    fields = (
        "id",
        "body",
        "convergence_expr",
        "max_iterations",
        "on_bound_reached",
    )
    has_fields = all(hasattr(constructed, f) for f in fields)
    frozen = getattr(type(constructed), "__dataclass_params__", None)
    is_frozen = bool(getattr(frozen, "frozen", False))

    result = {
        "probe": "probe1-unbounded-fixture",
        "unit_id": "IMP-0130",
        "violation_id": VIOLATION_LOOP_UNBOUNDED,
        "unbounded_ids": u_ids,
        "unbounded_yields_new_id": VIOLATION_LOOP_UNBOUNDED in u_ids,
        "bounded_twin_pass": b_viol == [],
        "convergence_only_pass": c_viol == [],
        "max_only_pass": m_viol == [],
        "type_refused_unbounded": type_refused,
        "loop_fields": list(fields),
        "constructed_has_fields": has_fields,
        "constructed_frozen": is_frozen,
        "pass": False,
    }
    ok = (
        VIOLATION_LOOP_UNBOUNDED in u_ids
        and b_viol == []
        and c_viol == []
        and m_viol == []
        and type_refused
        and has_fields
        and is_frozen
    )
    result["pass"] = ok
    print(json.dumps(result, indent=2, sort_keys=True))
    print(
        f"unbounded_ids={u_ids} bounded_ok={b_viol == []} "
        f"conv_only_ok={c_viol == []} max_only_ok={m_viol == []} "
        f"type_refused={type_refused} frozen={is_frozen}"
    )
    if not ok:
        print("FAILED:IMP-0130-probe1 unbounded Loop both-states")
        return 1
    print("SUCCESS:IMP-0130-probe1 unbounded fixture yields loop-unbounded; bounded twins pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
