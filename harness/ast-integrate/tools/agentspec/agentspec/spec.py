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

# What a node does when a unit under it fails. ``abort`` stops the siblings that have not
# started (they are SKIPPED, observably); ``continue`` lets them run. A workflow may set a
# ``default_on_failure`` that its composer applies to every child (IMP-0189).
ON_FAILURE_POLICIES: tuple[str, ...] = ("abort", "continue")
DEFAULT_ON_FAILURE = "abort"

# Node kinds the spec carried before Phase 7 and the four Phase-7 additions. The canonical
# exporter (:mod:`agentspec.canonical`) must round-trip every member of the union byte-for-byte
# (IMP-0146); a kind outside the union is refused on import, never coerced.
EXISTING_NODE_KINDS: frozenset[str] = frozenset({"WorkUnit", "FanOut", "Barrier", "Pipeline"})
NEW_NODE_KINDS: frozenset[str] = frozenset(
    {"Subworkflow", "Loop", "HumanCheckpoint", "DynamicFanOut"}
)
ALL_NODE_KINDS: frozenset[str] = EXISTING_NODE_KINDS | NEW_NODE_KINDS


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
    """One dispatchable unit of work.

    Two construction styles are legal and both round-trip:

    * the DISPATCH form (``prompt``, ``timeout_s``, ``receipt``) a runtime executes -- the
      defaults here are deliberately the values :func:`agentspec.validate.validate_workflow`
      REPORTS (``unit-timeout-missing`` for ``timeout_s == 0``, a vacuous receipt for a missing
      one), so omitting them is a validation finding, never a silent dispatch without a timeout;
    * the DECLARATIVE form (``prompt_ref``, ``routing``, ``tool_permissions``, ``on_failure``)
      the Phase-7 canonical document carries (IMP-0146).

    ``budget`` and ``budget_micro`` are one quantity under two names (``budget`` is the
    composer's spelling, IMP-0189); whichever is given is mirrored into the other.
    """

    id: str
    prompt: str = ""
    timeout_s: int = 0
    receipt: ReceiptSpec | None = None
    depends_on: tuple[str, ...] = ()
    budget_micro: int = 0
    isolation: str = "shared"
    writes: tuple[str, ...] = ()
    source_policy: tuple[str, ...] = ()
    owner_flags: tuple[str, ...] = ()
    prompt_ref: str = ""
    routing: Routing | None = None
    tool_permissions: tuple[str, ...] = ()
    on_failure: str = DEFAULT_ON_FAILURE
    budget: int = 0
    fail_family: str | None = None

    def __post_init__(self) -> None:
        if self.budget and not self.budget_micro:
            object.__setattr__(self, "budget_micro", self.budget)
        elif self.budget_micro and not self.budget:
            object.__setattr__(self, "budget", self.budget_micro)

    @property
    def kind(self) -> str:
        return "WorkUnit"


@dataclass(frozen=True, slots=True)
class FanOut:
    """Run ``units`` concurrently. The receipt set MUST equal the unit set."""

    id: str
    units: tuple[str, ...] = ()
    unit_ids: tuple[str, ...] = ()
    on_failure: str = DEFAULT_ON_FAILURE

    def __post_init__(self) -> None:
        if self.unit_ids and not self.units:
            object.__setattr__(self, "units", self.unit_ids)
        elif self.units and not self.unit_ids:
            object.__setattr__(self, "unit_ids", self.units)

    @property
    def kind(self) -> str:
        return "FanOut"


@dataclass(frozen=True, slots=True)
class UnitTemplate:
    id: str
    prompt_ref: str = ""


@dataclass(frozen=True, slots=True)
class DynamicFanOut:
    """Fan out over the items a producer unit emits.

    ``unit_template`` is either a :class:`UnitTemplate` (what
    :mod:`agentspec.dynamic_fanout` resolves) or the template's id as a string, which is how
    the canonical document spells it.
    """

    id: str
    producer_unit: str
    item_path: str
    unit_template: UnitTemplate | str
    max_cardinality: int = 64
    on_failure: str = DEFAULT_ON_FAILURE

    @property
    def kind(self) -> str:
        return "DynamicFanOut"


@dataclass(frozen=True, slots=True)
class Barrier:
    """Join on ``awaits``.

    ``null_tolerant`` defaults True: a unit that died and produced no result must not deadlock
    the join — the measured shape is one hung agent stalling a whole phase.

    ``wait_for`` is the canonical-document spelling of ``awaits``; either may be given and the
    other is filled in, so ``node.awaits`` is always the join set.
    """

    id: str
    awaits: tuple[str, ...] = ()
    policy: str = "all"
    null_tolerant: bool = True
    wait_for: tuple[str, ...] = ()
    on_failure: str = DEFAULT_ON_FAILURE

    def __post_init__(self) -> None:
        if self.wait_for and not self.awaits:
            object.__setattr__(self, "awaits", tuple(self.wait_for))
        elif self.awaits and not self.wait_for:
            object.__setattr__(self, "wait_for", tuple(self.awaits))

    @property
    def kind(self) -> str:
        return "Barrier"


@dataclass(frozen=True, slots=True)
class Pipeline:
    """Run ``stages`` in order. Distinct from a barrier: no cohort, so one slow stage cannot
    block a sibling cohort."""

    id: str
    stages: tuple[str, ...]
    on_failure: str = DEFAULT_ON_FAILURE

    @property
    def kind(self) -> str:
        return "Pipeline"


@dataclass(frozen=True, slots=True)
class Loop:
    """Bounded iteration. Construction of an unbounded Loop is refused."""

    id: str
    body: tuple[str, ...]
    convergence_expr: str | None
    max_iterations: int | None
    on_bound_reached: str = "abort"
    on_failure: str = DEFAULT_ON_FAILURE

    def __post_init__(self) -> None:
        if self.convergence_expr in (None, "") and self.max_iterations is None:
            raise ValueError("loop-unbounded")

    @property
    def kind(self) -> str:
        return "Loop"


@dataclass(frozen=True, slots=True)
class HumanCheckpoint:
    """Owner gate that pauses dispatch until an allowed response is recorded.

    A checkpoint has NO ``on_failure`` of its own: it never fails, it pauses, and
    ``default_if_unanswered`` is its whole policy. The field set is the frozen constructor
    contract IMP-0131 pins (exactly these five); the canonical wire form carries
    ``on_failure`` for it as the fixed :data:`DEFAULT_ON_FAILURE`.
    """

    id: str
    prompt_ref: str
    allowed_responses: tuple[str, ...]
    default_if_unanswered: str | None
    pause_token: str

    @property
    def kind(self) -> str:
        return "HumanCheckpoint"

    @property
    def on_failure(self) -> str:
        """Read-only wire constant: a checkpoint's failure policy is always the default."""
        return DEFAULT_ON_FAILURE


@dataclass(frozen=True, slots=True)
class ParamBinding:
    """Bind one parameter of an embedded workflow to a value the parent supplies."""

    name: str
    value: object


@dataclass(frozen=True, slots=True)
class Subworkflow:
    """Embed another workflow (``workflow_ref``) as one node of this one.

    ``id_namespace`` prefixes every embedded unit id so two embeddings of the same child never
    collide; :meth:`namespaced` is the ONE joining rule, shared by the composer
    (:mod:`agentspec.compose`) and the canonical document.
    """

    id: str
    workflow_ref: str
    param_bindings: tuple[ParamBinding, ...] = ()
    id_namespace: str = ""
    on_failure: str = DEFAULT_ON_FAILURE

    def __post_init__(self) -> None:
        if not self.workflow_ref:
            raise ValueError("subworkflow-ref-empty")

    @property
    def kind(self) -> str:
        return "Subworkflow"

    def namespaced(self, unit_id: str) -> str:
        """The embedded id of a child unit: ``<namespace>.<unit_id>`` (a namespace that already
        ends in ``.`` is used as-is; an empty namespace leaves the id untouched)."""
        if not self.id_namespace:
            return unit_id
        if self.id_namespace.endswith("."):
            return f"{self.id_namespace}{unit_id}"
        return f"{self.id_namespace}.{unit_id}"


Node = FanOut | Barrier | Pipeline | Loop | Subworkflow | HumanCheckpoint | DynamicFanOut


@dataclass(frozen=True, slots=True)
class Workflow:
    """A whole declarative workflow: units, the graph over them, and the budget ceiling.

    ``params`` declares the workflow's parameters (:class:`Param`); ``default_on_failure`` is
    the policy the composer applies to an embedded child's failure unless a per-family
    override says otherwise (IMP-0189).
    """

    id: str
    spec_version: str
    units: tuple[WorkUnit, ...]
    nodes: tuple[Node, ...]
    budget_micro: int = 0
    params: tuple[Param, ...] = ()
    default_on_failure: str = DEFAULT_ON_FAILURE

    @property
    def kind(self) -> str:
        return "Workflow"

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
    """A declared workflow parameter.

    ``id``/``name`` and ``kind``/``param_type`` are the graph-file and canonical-document
    spellings of the same two fields; give either and the other is filled in. ``secret_ref``
    is a :class:`SecretRef` in the graph form and a ``"env:NAME"`` string in the canonical form.
    """

    id: str = ""
    kind: str = "string"
    default: object | None = None
    required: bool = False
    secret_ref: SecretRef | str | None = None
    ref: dict | None = None
    name: str = ""
    param_type: str = ""
    enum: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        if not self.id and self.name:
            self.id = self.name
        elif not self.name and self.id:
            self.name = self.id
        if self.param_type:
            self.kind = self.param_type
        else:
            self.param_type = self.kind
        self.enum = tuple(self.enum)


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
