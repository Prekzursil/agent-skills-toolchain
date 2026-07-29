"""Backend-agnostic completion gate (CSIE-DESIGN §4/§8). Clauses 2-5; clause 1 (job terminal) is the
backend caller's precondition. Delegates the proven predicates in harness.contract — one impl each."""

from __future__ import annotations
from harness.contract import Unit, and_gate_artifact, schema_valid, floor_for
from backends.base import Result


def and_gate(unit: Unit, artifact_path: str | None) -> Result:
    if not artifact_path:
        return Result(unit_id=unit.id, ok=False, reason="no-artifact", size=0)
    ok, reason, size = and_gate_artifact(unit.id, artifact_path, floor_for(unit.lane))
    if not ok:
        return Result(
            unit_id=unit.id, ok=False, reason=reason, size=size, artifact=artifact_path
        )
    sok, sreason = schema_valid(unit, artifact_path)
    if not sok:
        return Result(
            unit_id=unit.id, ok=False, reason=sreason, size=size, artifact=artifact_path
        )
    return Result(
        unit_id=unit.id,
        ok=True,
        reason="and-gate-pass",
        size=size,
        artifact=artifact_path,
    )
