"""Validate a :class:`agentspec.spec.Workflow` and return sorted violation ids.

``VIOLATIONS`` is the CLOSED set of ids this module can emit. ``tests/test_validate.py``
asserts a one-to-one mapping between ``VIOLATIONS`` and its own negative-case corpus, so a
clause cannot be added without a test that exercises it and a test cannot claim an id the
validator never emits. That bidirectional lock is the anti-divergence guard.
"""

from __future__ import annotations

from agentspec import SPEC_VERSION
from agentspec.spec import (
    BARRIER_POLICIES,
    ISOLATIONS,
    RECEIPT_FORMATS,
    Barrier,
    FanOut,
    Pipeline,
    Workflow,
    WorkUnit,
    node_ids,
    unit_ids,
)

VIOLATIONS: tuple[str, ...] = (
    "barrier-awaits-unknown",
    "barrier-empty",
    "barrier-policy-unknown",
    "budget-total-negative",
    "budget-units-exceed-total",
    "fanout-empty",
    "fanout-unit-duplicate",
    "fanout-unit-unknown",
    "node-id-collides-unit",
    "node-id-duplicate",
    "node-id-empty",
    "pipeline-stage-unknown",
    "pipeline-too-short",
    "spec-version-unsupported",
    "unit-budget-negative",
    "unit-dep-cycle",
    "unit-dep-self",
    "unit-dep-unknown",
    "unit-id-duplicate",
    "unit-id-empty",
    "unit-isolation-unknown",
    "unit-prompt-empty",
    "unit-receipt-clause-vacuous",
    "unit-receipt-format-unknown",
    "unit-timeout-missing",
    "unit-worktree-no-writes",
    "workflow-id-empty",
    "workflow-no-units",
)


def validate_workflow(workflow: Workflow) -> tuple[str, ...]:
    """Return the sorted, deduplicated violation ids for ``workflow``."""
    found: list[str] = []
    if workflow.spec_version != SPEC_VERSION:
        found.append("spec-version-unsupported")
    if not workflow.id.strip():
        found.append("workflow-id-empty")
    if not workflow.units:
        found.append("workflow-no-units")
    if workflow.budget_micro < 0:
        found.append("budget-total-negative")
    elif (
        sum(u.budget_micro for u in workflow.units if u.budget_micro > 0)
        > workflow.budget_micro
    ):
        found.append("budget-units-exceed-total")

    known = set(unit_ids(workflow))
    for unit in workflow.units:
        found.extend(_validate_unit(unit, known))
    found.extend(_validate_duplicate_unit_ids(workflow))
    found.extend(_validate_cycles(workflow))
    found.extend(_validate_nodes(workflow, known))
    return tuple(sorted(set(found)))


def _validate_unit(unit: WorkUnit, known: set[str]) -> list[str]:
    found: list[str] = []
    if not unit.id.strip():
        found.append("unit-id-empty")
    if not unit.prompt.strip():
        found.append("unit-prompt-empty")
    if unit.timeout_s <= 0:
        found.append("unit-timeout-missing")
    if unit.budget_micro < 0:
        found.append("unit-budget-negative")
    if unit.isolation not in ISOLATIONS:
        found.append("unit-isolation-unknown")
    elif unit.isolation == "worktree" and not unit.writes:
        found.append("unit-worktree-no-writes")
    found.extend(_validate_receipt(unit))
    for dep in unit.depends_on:
        if dep == unit.id:
            found.append("unit-dep-self")
        elif dep not in known:
            found.append("unit-dep-unknown")
    return found


def _validate_receipt(unit: WorkUnit) -> list[str]:
    """A receipt spec must give the AND-gate a NON-VACUOUS content clause."""
    if unit.receipt.fmt not in RECEIPT_FORMATS:
        return ["unit-receipt-format-unknown"]
    if unit.receipt.is_vacuous():
        return ["unit-receipt-clause-vacuous"]
    return []


def _validate_duplicate_unit_ids(workflow: Workflow) -> list[str]:
    ids = unit_ids(workflow)
    if len(set(ids)) != len(ids):
        return ["unit-id-duplicate"]
    return []


def _validate_cycles(workflow: Workflow) -> list[str]:
    """Depth-first cycle detection over ``depends_on``.

    Self-edges are reported as ``unit-dep-self`` by :func:`_validate_unit` and are skipped
    here so one defect does not produce two ids.
    """
    edges = {
        unit.id: tuple(d for d in unit.depends_on if d != unit.id)
        for unit in workflow.units
    }
    state: dict[str, int] = {}

    def walk(node: str) -> bool:
        if state.get(node) == 1:
            return True
        if state.get(node) == 2:
            return False
        state[node] = 1
        for nxt in edges.get(node, ()):
            if nxt in edges and walk(nxt):
                return True
        state[node] = 2
        return False

    for unit_id in edges:
        if walk(unit_id):
            return ["unit-dep-cycle"]
    return []


def _validate_nodes(workflow: Workflow, known_units: set[str]) -> list[str]:
    found: list[str] = []
    ids = node_ids(workflow)
    if len(set(ids)) != len(ids):
        found.append("node-id-duplicate")
    addressable = known_units | set(ids)
    for node in workflow.nodes:
        if not node.id.strip():
            found.append("node-id-empty")
        elif node.id in known_units:
            found.append("node-id-collides-unit")
        found.extend(_validate_node_body(node, known_units, addressable))
    return found


def _validate_node_body(
    node: FanOut | Barrier | Pipeline, known_units: set[str], addressable: set[str]
) -> list[str]:
    if isinstance(node, FanOut):
        return _validate_fanout(node, known_units)
    if isinstance(node, Barrier):
        return _validate_barrier(node, addressable)
    return _validate_pipeline(node, known_units)


def _validate_fanout(node: FanOut, known_units: set[str]) -> list[str]:
    found: list[str] = []
    if not node.units:
        found.append("fanout-empty")
    if len(set(node.units)) != len(node.units):
        found.append("fanout-unit-duplicate")
    if any(u not in known_units for u in node.units):
        found.append("fanout-unit-unknown")
    return found


def _validate_barrier(node: Barrier, addressable: set[str]) -> list[str]:
    """A barrier may await a unit OR another node (a fan-out), so it uses ``addressable``."""
    found: list[str] = []
    if not node.awaits:
        found.append("barrier-empty")
    if node.policy not in BARRIER_POLICIES:
        found.append("barrier-policy-unknown")
    if any(a not in addressable for a in node.awaits):
        found.append("barrier-awaits-unknown")
    return found


def _validate_pipeline(node: Pipeline, known_units: set[str]) -> list[str]:
    found: list[str] = []
    if len(node.stages) < 2:
        found.append("pipeline-too-short")
    if any(s not in known_units for s in node.stages):
        found.append("pipeline-stage-unknown")
    return found
