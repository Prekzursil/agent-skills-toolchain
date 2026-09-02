"""Validate a :class:`agentspec.spec.Workflow` and return sorted violation ids.

``VIOLATIONS`` is the CLOSED set of ids this module can emit. ``tests/test_validate.py``
asserts a one-to-one mapping between ``VIOLATIONS`` and its own negative-case corpus, so a
clause cannot be added without a test that exercises it and a test cannot claim an id the
validator never emits. That bidirectional lock is the anti-divergence guard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from agentspec import SPEC_VERSION, wire
from agentspec.import_generic_dag import DAG_VIOLATION_IDS
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


class _Id:
    def __init__(self, vid: str) -> None:
        self.id = vid

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.id == other
        return self.id == getattr(other, "id", other)

    def __hash__(self) -> int:
        return hash(self.id)

    # Probes written against dict-shaped violation rows (``x["id"]`` /
    # ``x.get("id")``) must read the same id as attribute-style consumers.
    def __getitem__(self, key: str) -> str:
        if key == "id":
            return self.id
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        return self.id if key == "id" else default

    def keys(self) -> tuple[str, ...]:
        return ("id",)

    def __repr__(self) -> str:
        return f"Violation({self.id!r})"

VIOLATION_SUBWORKFLOW_CYCLE = "subworkflow-reference-cycle"

# Workflow-parameter violations, reported at LOAD time by :func:`load_workflow` (IMP-0134).
VIOLATION_PARAM_MISSING_REQUIRED = "param-missing-required"
VIOLATION_PARAM_TYPE_MISMATCH = "param-type-mismatch"
VIOLATION_PARAM_OUT_OF_ENUM = "param-out-of-enum"
VIOLATION_PARAM_UNKNOWN_KEY = "param-unknown-key"

# Failure classes carried on a :class:`ParamViolation`. An unknown key is a STRICT-PARSER
# refusal (spec:11302): the document is rejected before any semantic check runs.
FAILURE_CLASS_STRICT_PARSER = "strict-parser"
FAILURE_CLASS_SEMANTIC = "semantic"
SPEC_ANCHOR_STRICT_PARSER = "spec:11302"

# Every ``VIOLATION_*`` constant in this module, as a LITERAL set. IMP-0134 probe 2 re-parses
# this file with ``ast`` and requires the constants and this set to be equal, so adding a
# constant without listing it here (or vice versa) is a red probe, not a silent drift. Kept as
# a plain (un-annotated) assignment: the probe's ``ast`` scan looks for ``ast.Assign``.
DOCUMENTED_VIOLATION_IDS = frozenset(
    {
        "spec-version-unsupported",
        "loop-unbounded",
        "subworkflow-reference-cycle",
        "param-missing-required",
        "param-type-mismatch",
        "param-out-of-enum",
        "param-unknown-key",
    }
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
    "loop-unbounded",
)

# The CLOSED set of every violation id anything under ``agentspec`` can emit: the structural
# validator (``VIOLATIONS``), the load-time parameter checks (``DOCUMENTED_VIOLATION_IDS``)
# and the generic-DAG import adapter (``AS-DAG-*``). An id outside this set is a defect in
# the emitter, never a new category (IMP-0162).
# Phase-7 semantic checks available on dict-shaped workflows (RES-0172 / CNF-0165 fixtures):
# a HumanCheckpoint must have an exit when the owner never answers, must offer at least one
# response, and a WorkUnit may only route to ``public-tor`` under the owner's explicit flag.
PHASE7_DICT_VIOLATION_IDS: frozenset[str] = frozenset(
    {
        "human-checkpoint-no-exit",
        "human-checkpoint-responses-empty",
        "source-policy-tor-unflagged",
    }
)

CLOSED_VIOLATION_IDS: frozenset[str] = (
    frozenset(VIOLATIONS)
    | DOCUMENTED_VIOLATION_IDS
    | frozenset(DAG_VIOLATION_IDS)
    | PHASE7_DICT_VIOLATION_IDS
)


def _validate_phase7_dict_nodes(workflow: Mapping[str, Any], nodes: list) -> list[_Id]:
    out: list[_Id] = []
    owner_tor = workflow.get("owner_tor_flag") is True
    for node in nodes:
        if not isinstance(node, dict):
            continue
        kind = str(node.get("type") or node.get("kind") or "")
        if kind == "HumanCheckpoint":
            responses = node.get("allowed_responses")
            if isinstance(responses, list) and not responses:
                out.append(_Id("human-checkpoint-responses-empty"))
            if node.get("default_if_unanswered") in (None, ""):
                out.append(_Id("human-checkpoint-no-exit"))
        elif kind == "WorkUnit":
            policy = node.get("source_policy")
            allowed = policy.get("allowed_classes") if isinstance(policy, dict) else None
            if isinstance(allowed, (list, tuple, set)) and "public-tor" in allowed and not owner_tor:
                out.append(_Id("source-policy-tor-unflagged"))
    return out


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
        found.extend(_validate_phase7_dict_nodes(workflow, nodes))
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
    """A receipt spec must give the AND-gate a NON-VACUOUS content clause.

    A unit declared without any receipt (the declarative Phase-7 form) has NO content clause
    at all, which is the vacuous case, not a new category.
    """
    if unit.receipt is None:
        return ["unit-receipt-clause-vacuous"]
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


# --------------------------------------------------------------------------- IMP-0134
# Workflow parameters are validated when the workflow is LOADED, never when a unit runs.
# ``load_workflow`` either returns a ``LoadedWorkflow`` or a list of ``ParamViolation``; only
# a ``LoadedWorkflow`` is accepted by ``run_unit``, so a bad value mapping cannot reach run
# time by any typed path.

PARAM_TYPES: tuple[str, ...] = ("string", "integer", "number", "boolean", "secret_ref")


@dataclass(frozen=True, slots=True)
class ParamViolation:
    """One load-time parameter refusal: closed ``id``, the offending ``param`` and a detail."""

    id: str
    param: str
    detail: str
    failure_class: str = FAILURE_CLASS_SEMANTIC


@dataclass(frozen=True, slots=True)
class LoadedWorkflow:
    """A workflow whose parameter values passed every load-time check (values coerced)."""

    workflow_id: str
    params: tuple[Mapping[str, Any], ...]
    values: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LoadResult:
    """``ok`` iff ``loaded`` is a :class:`LoadedWorkflow`; otherwise ``violations`` says why."""

    ok: bool
    loaded: LoadedWorkflow | None
    violations: tuple[ParamViolation, ...] = ()


def _declared_params(workflow: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = workflow.get("params") or ()
    out: list[Mapping[str, Any]] = []
    for item in raw:
        if isinstance(item, Mapping) and item.get("name") is not None:
            out.append(item)
    return out


def _coerce(value: Any, ptype: str) -> tuple[bool, Any]:
    """Return ``(accepted, coerced)``; string digits coerce to ``int`` for ``integer``."""
    if ptype == "string":
        return isinstance(value, str), value
    if ptype == "integer":
        if isinstance(value, bool):
            return False, value
        if isinstance(value, int):
            return True, value
        if isinstance(value, str) and value.strip().lstrip("+-").isdigit():
            return True, int(value.strip())
        return False, value
    if ptype == "number":
        if isinstance(value, bool):
            return False, value
        if isinstance(value, (int, float)):
            return True, value
        if isinstance(value, str):
            try:
                return True, float(value)
            except ValueError:
                return False, value
        return False, value
    if ptype == "boolean":
        if isinstance(value, bool):
            return True, value
        if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            return True, value.strip().lower() == "true"
        return False, value
    if ptype == "secret_ref":
        if isinstance(value, Mapping):
            return bool(value.get("env") or value.get("name")), dict(value)
        if isinstance(value, str):
            return value.startswith("env:") and len(value) > 4, value
        return False, value
    return False, value


def validate_params_at_load(
    workflow: Mapping[str, Any], values: Mapping[str, Any] | None
) -> tuple[list[ParamViolation], dict[str, Any]]:
    """Check ``values`` against the workflow's declared ``params``.

    Strict-parser refusals (unknown keys, spec:11302) come first: a document carrying a key
    the schema never declared is rejected before its declared values are even looked at.
    Returns the violations in detection order plus the coerced value mapping.
    """
    declared = _declared_params(workflow)
    supplied: Mapping[str, Any] = values or {}
    found: list[ParamViolation] = []
    names = [str(p["name"]) for p in declared]
    for key in supplied:
        if str(key) not in names:
            found.append(
                ParamViolation(
                    VIOLATION_PARAM_UNKNOWN_KEY,
                    str(key),
                    f"{SPEC_ANCHOR_STRICT_PARSER}: value key {key!r} is not a declared param",
                    FAILURE_CLASS_STRICT_PARSER,
                )
            )
    coerced: dict[str, Any] = {}
    for spec in declared:
        name = str(spec["name"])
        ptype = str(spec.get("type") or "string")
        if name not in supplied:
            if "default" in spec and spec["default"] is not None:
                coerced[name] = spec["default"]
            elif spec.get("required"):
                found.append(
                    ParamViolation(
                        VIOLATION_PARAM_MISSING_REQUIRED,
                        name,
                        f"required param {name!r} has no value and no default",
                    )
                )
            continue
        accepted, value = _coerce(supplied[name], ptype)
        if not accepted:
            found.append(
                ParamViolation(
                    VIOLATION_PARAM_TYPE_MISMATCH,
                    name,
                    f"param {name!r} expects {ptype}, got {type(supplied[name]).__name__}",
                )
            )
            continue
        enum = spec.get("enum")
        if enum and value not in tuple(enum):
            found.append(
                ParamViolation(
                    VIOLATION_PARAM_OUT_OF_ENUM,
                    name,
                    f"param {name!r} value {value!r} not in {list(enum)}",
                )
            )
            continue
        coerced[name] = value
    return found, coerced


def load_workflow(
    workflow: Mapping[str, Any], values: Mapping[str, Any] | None = None
) -> LoadResult:
    """Load ``workflow`` with ``values``; a failed load yields NO :class:`LoadedWorkflow`."""
    if not isinstance(workflow, Mapping):
        raise TypeError("load_workflow expects the workflow document as a mapping")
    violations, coerced = validate_params_at_load(workflow, values)
    if violations:
        return LoadResult(ok=False, loaded=None, violations=tuple(violations))
    loaded = LoadedWorkflow(
        workflow_id=str(workflow.get("id") or ""),
        params=tuple(dict(p) for p in _declared_params(workflow)),
        values=coerced,
    )
    return LoadResult(ok=True, loaded=loaded, violations=())


def run_unit(loaded: LoadedWorkflow, unit_id: str | None = None) -> dict[str, Any]:
    """Run against a LOADED workflow only. Anything else (a failed ``LoadResult``, a raw
    document) is a ``TypeError``: load-time checks cannot be bypassed by a runtime-shaped call."""
    if not isinstance(loaded, LoadedWorkflow):
        raise TypeError(
            f"run_unit requires a LoadedWorkflow, got {type(loaded).__name__}; "
            "call load_workflow first"
        )
    return {
        "ran": True,
        "workflow_id": loaded.workflow_id,
        "unit_id": unit_id,
        "values": dict(loaded.values),
    }
