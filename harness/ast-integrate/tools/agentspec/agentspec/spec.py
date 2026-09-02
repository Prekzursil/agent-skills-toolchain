"""The vendor-neutral workflow SPEC — frozen declarative types, no behaviour.

**This spec is the SINGLE SOURCE OF TRUTH.** A runtime does not invent its own dialect: it
loads a :class:`Workflow`, validates it with :func:`agentspec.validate.validate_workflow`, and
TRANSLATES it to whatever its vendor rail needs. Two runtimes sharing this module cannot
diverge into rival dialects, which is the mitigation the second-runtime decision rests on.

Design rules, each with a measured reason:

* **Frozen + slots.** A work-unit result is a record. A counter mutated inside a helper is a
  measured loss class, and an immutable record makes the "no double-count" budget property
  checkable rather than hopeful.
* **Integers only for anything numeric on the wire.** `wall_ms`, `budget_micro`, `timeout_s`
  are `int`. An integral float round-trips as `1.0` in Python and `1` in JS — one of six
  measured Python/JS canonicalisation divergences (README).
* **No defaults that hide a hazard.** `timeout_s` has no default: "no dispatch without an
  explicit timeout" is a regression row (R6), so the type system asks for it.
* **A worktree unit declares its `writes`.** File-disjoint agents share one git index and a
  broad `git add` sweeps a sibling's files; the declaration is what makes a scoped add
  possible, so :mod:`agentspec.validate` requires it.
"""

from __future__ import annotations

from dataclasses import dataclass

RECEIPT_FORMATS: tuple[str, ...] = ("json", "text")
BARRIER_POLICIES: tuple[str, ...] = ("all", "any")
ISOLATIONS: tuple[str, ...] = ("shared", "worktree")
SPEC_VERSION_PRE_PHASE7 = 6
CURRENT_SPEC_VERSION = 11


@dataclass(frozen=True, slots=True)
class ReceiptSpec:
    """How a unit's receipt is recognised as a real work product.

    ``required_fields`` (json) and ``forbidden_markers`` (text) are what stop the completion
    AND-gate's content clause from being VACUOUS. Measured failure this prevents: a rail exits
    0 having written a non-empty text receipt that says "work is still in progress", and a
    two-clause gate reports SUCCESS.
    """

    fmt: str
    required_fields: tuple[str, ...] = ()
    forbidden_markers: tuple[str, ...] = ()

    def is_vacuous(self) -> bool:
        """True when this spec gives the AND-gate NO content clause for its own format.

        The ONE predicate shared by :func:`agentspec.validate.validate_workflow` (which
        reports ``unit-receipt-clause-vacuous``) and :func:`agentspec.oracle.judge` (which
        refuses outright), so a consumer that skips the Workflow layer cannot lose the catch.

        An unrecognised ``fmt`` is NOT vacuous: both call sites reject an unknown format
        first, and answering True here would report one defect as two ids.
        """
        if self.fmt == "json":
            return not self.required_fields
        if self.fmt == "text":
            return not self.forbidden_markers
        return False


@dataclass(frozen=True, slots=True)
class WorkUnit:
    """One dispatchable unit of work."""

    id: str
    prompt: str
    timeout_s: int
    receipt: ReceiptSpec
    depends_on: tuple[str, ...] = ()
    budget_micro: int = 0
    isolation: str = "shared"
    writes: tuple[str, ...] = ()
    source_policy: tuple[str, ...] = ()
    owner_flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FanOut:
    """Run ``units`` concurrently. The receipt set MUST equal the unit set."""

    id: str
    units: tuple[str, ...] = ()
    unit_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.unit_ids and not self.units:
            object.__setattr__(self, "units", self.unit_ids)
        elif self.units and not self.unit_ids:
            object.__setattr__(self, "unit_ids", self.units)


@dataclass(frozen=True, slots=True)
class UnitTemplate:
    id: str
    prompt_ref: str = ""


@dataclass(frozen=True, slots=True)
class DynamicFanOut:
    id: str
    producer_unit: str
    item_path: str
    unit_template: UnitTemplate
    max_cardinality: int = 64


@dataclass(frozen=True, slots=True)
class Barrier:
    """Join on ``awaits``.

    ``null_tolerant`` defaults True: a unit that died and produced no result must not deadlock
    the join — the measured shape is one hung agent stalling a whole phase.
    """

    id: str
    awaits: tuple[str, ...]
    policy: str = "all"
    null_tolerant: bool = True


@dataclass(frozen=True, slots=True)
class Pipeline:
    """Run ``stages`` in order. Distinct from a barrier: no cohort, so one slow stage cannot
    block a sibling cohort."""

    id: str
    stages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Loop:
    """Bounded iteration. Construction of an unbounded Loop is refused."""

    id: str
    body: tuple[str, ...]
    convergence_expr: str | None
    max_iterations: int | None
    on_bound_reached: str = "abort"

    def __post_init__(self) -> None:
        if self.convergence_expr in (None, "") and self.max_iterations is None:
            raise ValueError("loop-unbounded")


Node = FanOut | Barrier | Pipeline | Loop


@dataclass(frozen=True, slots=True)
class Workflow:
    """A whole declarative workflow: units, the graph over them, and the budget ceiling."""

    id: str
    spec_version: str
    units: tuple[WorkUnit, ...]
    nodes: tuple[Node, ...]
    budget_micro: int

    def to_json(self) -> dict:
        def node_json(node: object) -> dict:
            if isinstance(node, FanOut):
                return {"kind": "FanOut", "id": node.id, "units": list(node.units or node.unit_ids)}
            if isinstance(node, Barrier):
                return {"kind": "Barrier", "id": node.id, "awaits": list(node.awaits)}
            if isinstance(node, Pipeline):
                return {"kind": "Pipeline", "id": node.id, "stages": list(node.stages)}
            if isinstance(node, Loop):
                return {
                    "kind": "Loop",
                    "id": node.id,
                    "body": list(node.body),
                    "max_iterations": node.max_iterations,
                    "convergence_expr": node.convergence_expr,
                }
            return {"kind": type(node).__name__, "id": getattr(node, "id", "")}

        return {
            "id": self.id,
            "spec_version": self.spec_version,
            "budget_micro": self.budget_micro,
            "units": [
                {
                    "id": u.id,
                    "prompt": u.prompt,
                    "timeout_s": u.timeout_s,
                    "isolation": u.isolation,
                    "writes": list(u.writes),
                    "receipt": {
                        "fmt": u.receipt.fmt,
                        "required_fields": list(u.receipt.required_fields),
                        "forbidden_markers": list(u.receipt.forbidden_markers),
                    },
                }
                for u in self.units
            ],
            "nodes": [node_json(n) for n in self.nodes],
            "n": len(self.units),
        }


def unit_ids(workflow: Workflow) -> tuple[str, ...]:
    """Declared unit ids in declaration order (never sorted — order is data)."""
    return tuple(unit.id for unit in workflow.units)


def node_ids(workflow: Workflow) -> tuple[str, ...]:
    """Declared node ids in declaration order."""
    return tuple(node.id for node in workflow.nodes)


def unit_by_id(workflow: Workflow, unit_id: str) -> WorkUnit:
    """Look up a declared unit, raising :class:`KeyError` when it is absent."""
    for unit in workflow.units:
        if unit.id == unit_id:
            return unit
    raise KeyError(f"no work unit with id {unit_id!r}")


@dataclass(frozen=True, slots=True)
class HumanCheckpoint:
    """Owner gate that pauses dispatch until an allowed response is recorded."""

    id: str
    prompt_ref: str
    allowed_responses: tuple[str, ...]
    default_if_unanswered: str | None
    pause_token: str


FAILURE_POLICIES: tuple[str, ...] = (
    "fail-closed",
    "fail-open",
    "retry",
    "escalate-owner",
)
PHASE7_NODE_TYPES: tuple[str, ...] = (
    "FanOut",
    "Barrier",
    "Pipeline",
    "HumanCheckpoint",
    "WorkUnit",
)
SOURCE_CLASSES: tuple[str, ...] = (
    "public-web",
    "academic",
    "institutional",
    "owner-private",
    "public-tor",
)


@dataclass(frozen=True, slots=True)
class Routing:
    """Work-unit rail routing triple. Unknown vendor/model/role must fail closed."""

    vendor: str
    model: str
    role: str
    fallbacks: tuple[str, ...] = ()


@dataclass
class SecretRef:
    name: str
    source: str = "env"


@dataclass
class Param:
    id: str
    kind: str = "string"
    default: str | None = None
    required: bool = False
    secret_ref: SecretRef | None = None
    ref: dict | None = None


@dataclass
class GraphNode:
    kind: str
    id: str
    unit_ids: tuple[str, ...] = ()
    await_unit_ids: tuple[str, ...] = ()
    next: str | None = None
    body: tuple[str, ...] = ()


@dataclass
class GraphWorkflow:
    id: str
    units: tuple[str, ...]
    nodes: tuple[GraphNode, ...]
    params: tuple[Param, ...] = ()
    spec_version: str = "1"
    entry: str | None = None

    def unit_id_set(self) -> set[str]:
        return set(self.units)

    def node_id_set(self) -> set[str]:
        return {n.id for n in self.nodes}


def workflow_from_path(path) -> GraphWorkflow:
    import json
    from pathlib import Path

    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    nodes = []
    for raw in doc.get("nodes") or []:
        nodes.append(
            GraphNode(
                kind=str(raw.get("kind") or ""),
                id=str(raw.get("id") or ""),
                unit_ids=tuple(raw.get("unit_ids") or []),
                await_unit_ids=tuple(raw.get("await_unit_ids") or []),
                next=raw.get("next"),
                body=tuple(raw.get("body") or []),
            )
        )
    units = doc.get("units") or []
    unit_ids_t = tuple(
        u if isinstance(u, str) else str(u.get("id"))
        for u in units
    )
    params = []
    for raw in doc.get("params") or []:
        ref = raw.get("ref")
        secret = None
        if raw.get("kind") == "secret_ref" and isinstance(ref, dict):
            secret = SecretRef(name=str(ref.get("name") or ""), source=str(ref.get("source") or "env"))
        params.append(
            Param(
                id=str(raw.get("id") or ""),
                kind=str(raw.get("kind") or "string"),
                default=raw.get("default"),
                required=bool(raw.get("required")),
                secret_ref=secret,
                ref=ref if isinstance(ref, dict) else None,
            )
        )
    return GraphWorkflow(
        id=str(doc.get("id") or ""),
        units=unit_ids_t,
        nodes=tuple(nodes),
        params=tuple(params),
        spec_version=str(doc.get("spec_version") or "1"),
        entry=doc.get("entry"),
    )


def load_workflow(path) -> GraphWorkflow:
    return workflow_from_path(path)


class ToolPermissionError(Exception):
    """A tool was requested outside the effective (narrowed) permission set.

    ``code`` is the stable wire id probes assert (IMP-0136, TST-0223). Never
    confuse this with OS ``PermissionError`` on ``/root``; callers must pass a
    writable workspace, not a home/root path.
    """

    def __init__(
        self,
        message: str = "",
        code: str = "tool-permission-denied",
        tool: str | None = None,
    ) -> None:
        super().__init__(message or code)
        self.code = code
        self.tool = tool


def freeze_tool_permissions(value: object) -> frozenset[str]:
    """Freeze a permission bag. Strings become a singleton; None is empty."""
    if value is None:
        return frozenset()
    if isinstance(value, str):
        return frozenset({value})
    return frozenset(str(item) for item in value)
