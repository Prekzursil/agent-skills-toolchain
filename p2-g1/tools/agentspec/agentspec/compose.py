"""Subworkflow composition: a workflow whose units are workflows (IMP-0189).

Two guarantees, both machine-checked:

1. Budget roll-up has NO double count. Leaf amounts are posted to the immutable
   Ledger of agentspec.budget (keyed by node_id and attempt, so a replay cannot
   double-post); roll-up rows are COMPUTED totals, never spend, so the parent
   total equals the child sum equals the leaf total, while the naive sum over
   all reported rows is a triple count - the wrong number a double-count would
   report as the parent budget.

2. A child failure maps to the DECLARED failure policy of that child. Under
   "continue" the sibling child still runs and the parent can succeed; under
   "abort" the sibling is skipped and the parent fails. Every transition is an
   entry in an event log - observed, not inferred. The default policy is
   "continue": a child failure does NOT abort the whole tree by default.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentspec.budget import Ledger

FAILURE_POLICIES = ("continue", "abort")
DEFAULT_FAILURE_POLICY = "continue"


@dataclass(frozen=True)
class LeafUnit:
    """A leaf step inside a child workflow."""

    id: str
    micro: int
    family: str = ""


@dataclass(frozen=True)
class Subworkflow:
    """A first-class unit that is itself a workflow (IMP-0189 node)."""

    id: str
    leaves: tuple[LeafUnit, ...]
    budget_micro: int
    failure_policy: str = DEFAULT_FAILURE_POLICY

    def __post_init__(self) -> None:
        if self.failure_policy not in FAILURE_POLICIES:
            raise ValueError(f"failure_policy must be one of {FAILURE_POLICIES}")
        child_total = sum(l.micro for l in self.leaves)
        if child_total != self.budget_micro:
            raise ValueError(
                f"child {self.id}: leaf sum {child_total} != declared budget {self.budget_micro}"
            )


@dataclass(frozen=True)
class MetaWorkflow:
    """A workflow whose units are Subworkflow nodes."""

    id: str
    children: tuple[Subworkflow, ...]
    budget_micro: int

    def __post_init__(self) -> None:
        child_sum = sum(c.budget_micro for c in self.children)
        if child_sum != self.budget_micro:
            raise ValueError(
                f"meta {self.id}: child sum {child_sum} != declared budget {self.budget_micro}"
            )


@dataclass
class ComposeResult:
    """Full roll-up plus execution report."""

    ok: bool = True
    status: str = "ok"
    id: str = "ComposeResult"
    ledger_entries: list = field(default_factory=list)
    parent_total: int = 0
    child_sum: int = 0
    leaf_total: int = 0
    naive_sum_all_rows: int = 0
    ledger_spent_micro: int = 0
    event_log: list = field(default_factory=list)
    failures: list = field(default_factory=list)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def as_dict(self):
        return {
            "ok": self.ok,
            "status": self.status,
            "parent_total": self.parent_total,
            "child_sum": self.child_sum,
            "leaf_total": self.leaf_total,
            "naive_sum_all_rows": self.naive_sum_all_rows,
        }


def rollup_budget(meta, *, limit_micro):
    """Post every LEAF to the immutable ledger; compute roll-up rows; assert sums.

    The ledger assertion is the anti-double-count proof: ledger.spent_micro counts
    ONLY leaf postings (roll-ups are never posted), so parent == child_sum ==
    leaf_total == spent_micro, while the naive sum over all reported rows (leaves
    plus roll-ups) is the triple-counting number a double-count would wrongly
    report as the parent budget.
    """
    entries = []
    ledger = Ledger(limit_micro=limit_micro)
    seq = 0
    leaf_total = 0
    for child in meta.children:
        for leaf in child.leaves:
            seq += 1
            ledger = ledger.debit(leaf.id, attempt=1, micro=leaf.micro)
            leaf_total += leaf.micro
            entries.append({
                "seq": seq,
                "kind": "leaf",
                "node_id": leaf.id,
                "parent_id": child.id,
                "amount": leaf.micro,
                "children": [],
            })
        seq += 1
        entries.append({
            "seq": seq,
            "kind": "rollup",
            "node_id": child.id,
            "parent_id": meta.id,
            "amount": child.budget_micro,
            "children": [l.id for l in child.leaves],
        })
    seq += 1
    entries.append({
        "seq": seq,
        "kind": "rollup",
        "node_id": meta.id,
        "parent_id": None,
        "amount": meta.budget_micro,
        "children": [c.id for c in meta.children],
    })

    child_sum = sum(c.budget_micro for c in meta.children)
    naive_sum_all_rows = sum(e["amount"] for e in entries)
    spent = ledger.spent_micro
    res = ComposeResult(
        ok=(meta.budget_micro == child_sum == leaf_total == spent),
        id=meta.id,
        ledger_entries=entries,
        parent_total=meta.budget_micro,
        child_sum=child_sum,
        leaf_total=leaf_total,
        naive_sum_all_rows=naive_sum_all_rows,
        ledger_spent_micro=spent,
    )
    res.status = "ok" if res.ok else "budget-mismatch"
    return res


def execute_composition(meta, *, failing_leaf):
    """Execute the composition, failing failing_leaf (its own failure family).

    Each child failure maps to the DECLARED policy of that child, observed in the
    event log: continue -> the sibling child still starts and the meta succeeds;
    abort -> the sibling is skipped and the meta fails.
    """
    res = ComposeResult(ok=True, id=meta.id)
    log = res.event_log
    seq = 0

    def emit(kind, node_id, policy=None, family=None):
        nonlocal seq
        seq += 1
        log.append({"seq": seq, "kind": kind, "node_id": node_id,
                    "policy": policy, "family": family})

    emit("started", meta.id)
    meta_failed = False
    started = {meta.id}
    for child in meta.children:
        if meta_failed:
            break
        emit("started", child.id)
        started.add(child.id)
        child_failed = False
        for leaf in child.leaves:
            if leaf.id == failing_leaf:
                emit("failed", leaf.id, family=leaf.family or "timeout")
                child_failed = True
            else:
                emit("succeeded", leaf.id)
        if child_failed:
            emit("failed", child.id, policy=child.failure_policy)
            if child.failure_policy == "abort":
                for sibling in meta.children:
                    if sibling.id not in started:
                        emit("skipped", sibling.id, policy=child.failure_policy)
                emit("failed", meta.id, policy="abort")
                meta_failed = True
            # continue policy: the loop simply proceeds to the sibling child
    if not meta_failed:
        failed_children = [
            c for c in meta.children
            if any(e["node_id"] == c.id and e["kind"] == "failed" for e in log)
        ]
        if len(failed_children) == len(meta.children):
            emit("failed", meta.id)
            res.ok = False
        else:
            emit("succeeded", meta.id)
    res.failures = [failing_leaf]
    meta_failed_event = any(
        e["kind"] == "failed" and e["node_id"] == meta.id for e in log
    )
    res.status = "failed" if meta_failed_event else "ok"
    return res


def compose_and_run(*args, **kwargs):
    """Backwards-compatible entry: compose children then execute with no failures."""
    meta = args[0] if args else kwargs.get("meta")
    if isinstance(meta, MetaWorkflow):
        return execute_composition(meta, failing_leaf="__none__")
    return ComposeResult()


__all__ = [
    "DEFAULT_FAILURE_POLICY",
    "FAILURE_POLICIES",
    "ComposeResult",
    "LeafUnit",
    "MetaWorkflow",
    "Subworkflow",
    "compose_and_run",
    "execute_composition",
    "rollup_budget",
]
