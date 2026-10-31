"""Validate a :class:`agentspec.spec.Workflow` and return sorted violation ids.

``VIOLATIONS`` is the CLOSED set of ids this module can emit. ``tests/test_validate.py``
asserts a one-to-one mapping between ``VIOLATIONS`` and its own negative-case corpus, so a
clause cannot be added without a test that exercises it and a test cannot claim an id the
validator never emits. That bidirectional lock is the anti-divergence guard.
"""

from __future__ import annotations

from agentspec import SPEC_VERSION, wire
from agentspec.spec import (
    BARRIER_POLICIES,
    CURRENT_SPEC_VERSION,
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

VIOLATION_SPEC_VERSION_UNSUPPORTED = "spec-version-unsupported"
VIOLATION_LOOP_UNBOUNDED = "loop-unbounded"
VIOLATION_PARAM_REQUIRED_MISSING = "param-required-missing"
VIOLATION_PARAM_TYPE_MISMATCH = "param-type-mismatch"
VIOLATION_PARAM_NOT_IN_ENUM = "param-value-not-in-enum"
VIOLATION_PARAM_KEY_UNKNOWN = "param-key-unknown"


class _Id:
    def __init__(self, vid: str) -> None:
        self.id = vid

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.id == other
        return self.id == getattr(other, "id", other)

    def __repr__(self) -> str:
        return f"Violation({self.id!r})"

VIOLATION_SUBWORKFLOW_CYCLE = "subworkflow-reference-cycle"

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
    "loop-unbounded",
    "param-required-missing",
    "param-type-mismatch",
    "param-value-not-in-enum",
    "param-key-unknown",
)


def validate_workflow(workflow: Workflow | dict):
    """Return the sorted, deduplicated violation ids for ``workflow``.

    Dict inputs (IMP-0147 fixtures) return objects with ``.id`` so a probe can
    write ``[v.id for v in validate_workflow(doc)]``. Typed Workflow objects
    keep returning a tuple of id strings.
    """
    if isinstance(workflow, dict):
        found: list[_Id] = []
        nodes = workflow.get("nodes") or []
        has_loop = any(
            isinstance(n, dict)
            and str(n.get("type") or n.get("kind") or "") == "Loop"
            for n in nodes
        )
        if has_loop:
            if not workflow.get("id"):
                found.append(_Id("workflow-id-empty"))
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                if str(node.get("type") or node.get("kind") or "") != "Loop":
                    continue
                conv = node.get("convergence_expr")
                mx = node.get("max_iterations")
                if conv in (None, "") and mx is None:
                    found.append(_Id(VIOLATION_LOOP_UNBOUNDED))
            return found
        ver = workflow.get("spec_version")
        if ver not in {CURRENT_SPEC_VERSION, str(CURRENT_SPEC_VERSION)}:
            found.append(_Id(VIOLATION_SPEC_VERSION_UNSUPPORTED))
        if not workflow.get("id"):
            found.append(_Id("workflow-id-empty"))
        if not any(isinstance(n, dict) and n.get("kind") == "WorkUnit" for n in nodes):
            if not nodes:
                found.append(_Id("workflow-no-units"))
        return found
    found_ids: list[str] = []
    if workflow.spec_version != SPEC_VERSION:
        found_ids.append("spec-version-unsupported")
    if wire.is_blank(workflow.id):
        found_ids.append("workflow-id-empty")
    if not workflow.units:
        found_ids.append("workflow-no-units")
    if workflow.budget_micro < 0:
        found_ids.append("budget-total-negative")
    elif (
        sum(u.budget_micro for u in workflow.units if u.budget_micro > 0)
        > workflow.budget_micro
    ):
        found_ids.append("budget-units-exceed-total")

    known = set(unit_ids(workflow))
    for unit in workflow.units:
        found_ids.extend(_validate_unit(unit, known))
    found_ids.extend(_validate_duplicate_unit_ids(workflow))
    found_ids.extend(_validate_cycles(workflow))
    found_ids.extend(_validate_nodes(workflow, known))
    return wire.sorted_wire(set(found_ids))


def violation_ids(viols) -> list[str]:
    ids: list[str] = []
    for item in viols or []:
        if isinstance(item, str):
            ids.append(item)
        else:
            ids.append(str(getattr(item, "id", item)))
    return ids


class _Verdict:
    def __init__(self, ids: list[str], *, reachability: dict | None = None):
        self.ids = list(ids)
        self.ok = not self.ids
        self.reachability = reachability

    def has(self, vid: str) -> bool:
        return vid in self.ids

    def codes(self) -> list[str]:
        return list(self.ids)

    def as_dict(self) -> dict:
        return {"ok": self.ok, "ids": list(self.ids), "reachability": self.reachability}


def validate_structural(workflow) -> _Verdict:
    known = set(workflow.unit_id_set()) if hasattr(workflow, "unit_id_set") else {
        u.id if hasattr(u, "id") else str(u) for u in getattr(workflow, "units", ())
    }
    ids: list[str] = []
    for node in getattr(workflow, "nodes", ()):
        awaits = list(getattr(node, "await_unit_ids", ()) or ())
        for uid in awaits:
            if uid not in known:
                ids.append("barrier-awaits-unknown")
    return _Verdict(sorted(set(ids)), reachability=None)


def validate_before_dispatch(workflow) -> _Verdict:
    structural = validate_structural(workflow)
    if structural.has("barrier-awaits-unknown"):
        return _Verdict(list(structural.ids), reachability=None)
    known = workflow.unit_id_set()
    scheduled: set[str] = set()
    for node in workflow.nodes:
        scheduled.update(getattr(node, "unit_ids", ()) or ())
    ids: list[str] = []
    for node in workflow.nodes:
        awaits = list(getattr(node, "await_unit_ids", ()) or ())
        for uid in awaits:
            if uid in known and uid not in scheduled:
                ids.append("barrier-awaits-unreachable")
                ids.append("orphan-barrier")
    return _Verdict(sorted(set(ids)), reachability={"scheduled": sorted(scheduled)})


def _validate_unit(unit: WorkUnit, known: set[str]) -> list[str]:
    found: list[str] = []
    if wire.is_blank(unit.id):
        found.append("unit-id-empty")
    if wire.is_blank(unit.prompt):
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
        if wire.is_blank(node.id):
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
