"""Meta-workflow composition: a workflow whose nodes embed other workflows (IMP-0189).

A :class:`~agentspec.spec.Subworkflow` node names a child workflow by ``workflow_ref``; the
composer resolves the reference in a *registry* (``{workflow_id: Workflow}``), runs the child
under the node's ``id_namespace`` and posts its spend to ONE immutable
:class:`~agentspec.budget.BudgetLedger`:

* every child unit is a **leaf** row, keyed by the namespaced id
  (``Subworkflow.namespaced(unit.id)``) so two embeddings of the same child never collide;
* every node (and the root) is a **roll-up** row whose amount the ledger computes from the rows
  already posted for its children -- the composer never supplies a total, so the parent budget
  cannot disagree with the leaves under it and a leaf can never be counted twice.

Failure policy is decided where the failure is observed and recorded in the event log:

* a unit that fails inside a child follows the NODE's ``on_failure`` -- ``abort`` skips the
  child's remaining units, ``continue`` runs them;
* a child node that fails follows the PARENT workflow's policy: a per-family
  ``policy_override`` (``{"timeout": "continue"}``) first, else the parent's
  ``default_on_failure``. ``abort`` skips the siblings that have not started (each gets an
  observable ``skipped`` event); ``continue`` lets them run.

Every state change is a :class:`ComposeEvent` with a 1-based ``seq``, so "the sibling started
AFTER the failure" is a comparison of two recorded sequence numbers, not an inference.

Pure and deterministic: no clock, no entropy, no I/O. The unit outcome comes from a pluggable
``runner``; the default reads the unit's declared ``fail_family`` (the spec-level simulation
the probes use), a real runtime passes its own.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from agentspec import taxonomy
from agentspec.budget import BudgetLedger, LedgerEntry
from agentspec.spec import ON_FAILURE_POLICIES, Subworkflow, Workflow, WorkUnit

EVENT_KINDS: tuple[str, ...] = ("started", "succeeded", "failed", "skipped")
"""The closed set of event kinds the composer records."""

BUDGET_EXHAUSTED = "budget-exhausted"
"""Family a child fails with when its leaf spend exceeds its declared ``budget_micro``."""

Runner = Callable[[WorkUnit, str], "str | None"]
"""``runner(unit, embedded_id) -> failure code or None``; ``None`` means the unit succeeded."""


class ComposeError(ValueError):
    """The composition itself is invalid (not a child failure). Carries a taxonomy-shaped reason."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class ComposeEvent:
    """One recorded state change. ``seq`` is 1-based and strictly increasing per run."""

    seq: int
    kind: str
    node_id: str
    family: str | None = None
    policy: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "kind": self.kind,
            "node_id": self.node_id,
            "family": self.family,
            "policy": self.policy,
        }


@dataclass(frozen=True, slots=True)
class ComposeResult:
    """What one composed run observed. ``ok`` is "ran to completion under policy": a child
    failure tolerated by ``continue`` keeps ``ok`` True; an ``abort`` makes it False."""

    root_id: str
    ok: bool
    aborted: bool
    policy_applied: str | None
    parent_budget: int
    child_budgets: dict[str, int]
    ledger: BudgetLedger
    events: tuple[ComposeEvent, ...]
    failed_nodes: tuple[str, ...] = ()
    skipped_nodes: tuple[str, ...] = ()
    failures: dict[str, str] = field(default_factory=dict)

    def events_for(self, node_id: str, kind: str | None = None) -> tuple[ComposeEvent, ...]:
        """The events recorded for ``node_id``, optionally only those of one ``kind``."""
        return tuple(
            e for e in self.events if e.node_id == node_id and (kind is None or e.kind == kind)
        )

    def to_json(self) -> dict[str, Any]:
        """Deterministic document: no clock, no paths, key order fixed by the caller's dumps."""
        return {
            "root_id": self.root_id,
            "ok": self.ok,
            "aborted": self.aborted,
            "policy_applied": self.policy_applied,
            "parent_budget": self.parent_budget,
            "child_budgets": dict(self.child_budgets),
            "leaf_total": self.ledger.leaf_total(),
            "naive_sum_all_rows": self.ledger.naive_sum_all_rows(),
            "failed_nodes": list(self.failed_nodes),
            "skipped_nodes": list(self.skipped_nodes),
            "failures": dict(self.failures),
            "events": [e.to_json() for e in self.events],
            "ledger": [
                {
                    "seq": row.seq,
                    "node_id": row.node_id,
                    "kind": row.kind,
                    "amount": row.amount,
                    "parent_id": row.parent_id,
                    "children": list(row.children),
                }
                for row in self.ledger.entries
            ],
        }


def declared_outcome(unit: WorkUnit, embedded_id: str) -> str | None:
    """The default runner: a unit fails with its declared ``fail_family``, else succeeds."""
    del embedded_id  # the declared outcome does not depend on where the unit is embedded
    return unit.fail_family or None


def _policy(value: object, where: str) -> str:
    if not isinstance(value, str) or value not in ON_FAILURE_POLICIES:
        raise ComposeError(
            "compose-policy-unknown",
            f"{where} must be one of {list(ON_FAILURE_POLICIES)}",
        )
    return value


def _lookup(registry: Mapping[str, Workflow], ref: str, where: str) -> Workflow:
    try:
        workflow = registry[ref]
    except KeyError:
        raise ComposeError("compose-ref-unknown", f"{where} references {ref!r}") from None
    if not isinstance(workflow, Workflow):
        raise ComposeError("compose-ref-unknown", f"registry[{ref!r}] is not a Workflow")
    return workflow


class _Composer:
    """One run's mutable state: the ledger, the event log and the policy outcome."""

    def __init__(
        self,
        registry: Mapping[str, Workflow],
        policy_override: Mapping[str, str] | None,
        runner: Runner,
    ) -> None:
        self.registry = registry
        self.override = {
            str(k): _policy(v, f"policy_override[{k!r}]")
            for k, v in (policy_override or {}).items()
        }
        self.runner = runner
        self.ledger = BudgetLedger()
        self.events: list[ComposeEvent] = []
        self.aborted = False
        self.policy_applied: str | None = None
        self.failed_nodes: list[str] = []
        self.skipped_nodes: list[str] = []
        self.failures: dict[str, str] = {}

    # ------------------------------------------------------------------ event log
    def emit(
        self, kind: str, node_id: str, *, family: str | None = None, policy: str | None = None
    ) -> ComposeEvent:
        if kind not in EVENT_KINDS:
            raise ComposeError("compose-event-kind-unknown", f"{kind!r} for {node_id!r}")
        event = ComposeEvent(len(self.events) + 1, kind, node_id, family, policy)
        self.events.append(event)
        return event

    # ------------------------------------------------------------------ policies
    def parent_policy(self, parent: Workflow, family: str) -> str:
        """Override by exact code, then by taxonomy member, else the parent's default."""
        for key in (family, taxonomy.family(family)):
            if key and key in self.override:
                return self.override[key]
        return _policy(parent.default_on_failure, f"{parent.id}.default_on_failure")

    # ------------------------------------------------------------------ running
    def run_unit(self, unit: WorkUnit, embedded_id: str, parent_id: str, policy: str) -> str | None:
        """Run one leaf: post its spend once, record the outcome; return the failure code."""
        self.emit("started", embedded_id)
        self.ledger.post_leaf(embedded_id, int(unit.budget_micro), parent_id=parent_id)
        code = self.runner(unit, embedded_id)
        if code:
            code = str(code)
            self.failures[embedded_id] = code
            self.emit("failed", embedded_id, family=code, policy=policy)
            return code
        self.emit("succeeded", embedded_id)
        return None

    def run_workflow(
        self,
        workflow: Workflow,
        *,
        node_id: str,
        parent_id: str | None,
        namespace: Callable[[str], str],
        unit_policy: str,
        chain: tuple[str, ...],
    ) -> tuple[str | None, LedgerEntry]:
        """Run ``workflow`` as node ``node_id``; return ``(failure code or None, roll-up row)``.

        ``chain`` is the ref path from the root, so a workflow that (transitively) embeds
        itself is refused as ``compose-ref-cyclic`` instead of recursing forever.
        """
        if workflow.id in chain:
            raise ComposeError(
                "compose-ref-cyclic", " -> ".join((*chain, workflow.id))
            )
        chain = (*chain, workflow.id)
        children: list[str] = []
        failure: str | None = None
        skipping = False

        for unit in workflow.units:
            embedded = namespace(unit.id)
            if skipping:
                self.emit("skipped", embedded, policy=unit_policy)
                self.skipped_nodes.append(embedded)
                continue
            code = self.run_unit(unit, embedded, node_id, unit_policy)
            children.append(embedded)
            if code and failure is None:
                failure = code
                if unit_policy == "abort":
                    skipping = True

        for node in workflow.nodes:
            if not isinstance(node, Subworkflow):
                continue  # graph nodes over the units above carry no spend of their own
            child_id = namespace(node.id)
            if skipping:
                self.emit("skipped", child_id, policy=unit_policy)
                self.skipped_nodes.append(child_id)
                continue
            code = self.run_child(workflow, node, child_id, node_id, namespace, chain)
            children.append(child_id)
            if code and failure is None:
                failure = code
                if unit_policy == "abort":
                    skipping = True

        rollup = self.ledger.post_rollup(node_id, tuple(children), parent_id=parent_id)
        if failure is None and 0 < int(workflow.budget_micro) < rollup.amount:
            failure = BUDGET_EXHAUSTED
            self.failures[node_id] = failure
        return failure, rollup

    def run_child(
        self,
        parent: Workflow,
        node: Subworkflow,
        child_id: str,
        parent_node_id: str,
        outer_namespace: Callable[[str], str],
        chain: tuple[str, ...],
    ) -> str | None:
        """Run one embedded child; return its failure code (already policy-recorded) or None."""
        child = _lookup(self.registry, node.workflow_ref, f"{child_id}.workflow_ref")
        declared = {p.name or p.id for p in child.params}
        for binding in node.param_bindings:
            if binding.name not in declared:
                raise ComposeError(
                    "compose-binding-unknown-param",
                    f"{child_id} binds {binding.name!r}, which {child.id!r} does not declare",
                )
        self.emit("started", child_id)
        failure, _rollup = self.run_workflow(
            child,
            node_id=child_id,
            parent_id=parent_node_id,
            namespace=lambda uid: outer_namespace(node.namespaced(uid)),
            unit_policy=_policy(node.on_failure, f"{child_id}.on_failure"),
            chain=chain,
        )
        if failure is None:
            self.emit("succeeded", child_id)
            return None
        policy = self.parent_policy(parent, failure)
        self.failed_nodes.append(child_id)
        self.failures.setdefault(child_id, failure)
        self.emit("failed", child_id, family=failure, policy=policy)
        self.policy_applied = policy
        return failure

    def run_root(self, root: Workflow) -> ComposeResult:
        """Run the root workflow: its own units, then its embedded children, under its policy."""
        root_policy = _policy(root.default_on_failure, f"{root.id}.default_on_failure")
        children: list[str] = []
        skipping = False

        for unit in root.units:
            if skipping:
                self.emit("skipped", unit.id, policy="abort")
                self.skipped_nodes.append(unit.id)
                continue
            code = self.run_unit(unit, unit.id, root.id, root_policy)
            children.append(unit.id)
            if code:
                policy = self.parent_policy(root, code)
                self.failed_nodes.append(unit.id)
                self.policy_applied = policy
                if policy == "abort":
                    self.aborted = True
                    skipping = True

        for node in root.nodes:
            if not isinstance(node, Subworkflow):
                continue
            if skipping:
                self.emit("skipped", node.id, policy="abort")
                self.skipped_nodes.append(node.id)
                continue
            code = self.run_child(root, node, node.id, root.id, lambda uid: uid, (root.id,))
            children.append(node.id)
            if code and self.policy_applied == "abort":
                self.aborted = True
                skipping = True

        rollup = self.ledger.post_rollup(root.id, tuple(children), parent_id=None)
        if 0 < int(root.budget_micro) < rollup.amount:
            self.failures[root.id] = BUDGET_EXHAUSTED
            self.failed_nodes.append(root.id)
        child_budgets = {
            node.id: (self.ledger.total_for(node.id) if node.id in self.ledger else 0)
            for node in root.nodes
            if isinstance(node, Subworkflow)
        }
        return ComposeResult(
            root_id=root.id,
            ok=not self.aborted and root.id not in self.failures,
            aborted=self.aborted,
            policy_applied=self.policy_applied,
            parent_budget=rollup.amount,
            child_budgets=child_budgets,
            ledger=self.ledger,
            events=tuple(self.events),
            failed_nodes=tuple(self.failed_nodes),
            skipped_nodes=tuple(self.skipped_nodes),
            failures=dict(self.failures),
        )


def compose_and_run(
    registry: Mapping[str, Workflow],
    root_id: str,
    *,
    policy_override: Mapping[str, str] | None = None,
    runner: Runner = declared_outcome,
) -> ComposeResult:
    """Compose ``registry[root_id]`` with its embedded children and run it.

    ``policy_override`` maps a failure code or taxonomy family to ``"abort"``/``"continue"``
    and beats the root's ``default_on_failure`` for that family. ``runner`` decides each unit's
    outcome (default: the unit's declared ``fail_family``).
    """
    root = _lookup(registry, root_id, "root_id")
    return _Composer(registry, policy_override, runner).run_root(root)


__all__ = [
    "BUDGET_EXHAUSTED",
    "EVENT_KINDS",
    "ComposeError",
    "ComposeEvent",
    "ComposeResult",
    "Runner",
    "compose_and_run",
    "declared_outcome",
]
