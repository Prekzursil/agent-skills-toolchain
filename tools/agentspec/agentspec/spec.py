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


@dataclass(frozen=True, slots=True)
class FanOut:
    """Run ``units`` concurrently. The receipt set MUST equal the unit set."""

    id: str
    units: tuple[str, ...]


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


Node = FanOut | Barrier | Pipeline


@dataclass(frozen=True, slots=True)
class Workflow:
    """A whole declarative workflow: units, the graph over them, and the budget ceiling."""

    id: str
    spec_version: str
    units: tuple[WorkUnit, ...]
    nodes: tuple[Node, ...]
    budget_micro: int


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
