"""Nested Subworkflow executor with namespacing, budget roll-up, and permission bounds.

Artifact writes stay under the caller-supplied ``artifacts_root``. This module
never stats ``/root`` or ``~/.claude``; G-1 remesure is not root.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from agentspec.permission_bound import narrow
from agentspec.spec import ToolPermissionError, freeze_tool_permissions


@dataclass
class ExecuteOpts:
    namespacing: bool = True
    count_rollups_as_spend: bool = False


@dataclass
class Task:
    id: str
    budget: int = 1
    write_name: str = "out.txt"
    write_from_param: str = "label"
    attempted_tool: str = ""


@dataclass
class Subworkflow:
    id: str
    workflow_ref: str
    id_namespace: str = ""
    param_bindings: dict[str, Any] = field(default_factory=dict)
    tool_permissions: frozenset[str] = field(default_factory=frozenset)


@dataclass
class Workflow:
    id: str
    nodes: tuple[Any, ...] = ()


@dataclass
class _Spend:
    kind: str
    unit_id: str
    amount: int
    parent_id: str | None = None


class SpendLedger:
    """Leaf spends are the only additive amounts; roll-ups are derived views."""

    def __init__(self) -> None:
        self._rows: list[_Spend] = []

    def add_leaf(self, unit_id: str, amount: int, parent_id: str | None = None) -> None:
        self._rows.append(
            _Spend(kind="leaf", unit_id=unit_id, amount=int(amount), parent_id=parent_id)
        )

    def add_rollup(self, unit_id: str, amount: int, parent_id: str | None = None) -> None:
        self._rows.append(
            _Spend(kind="rollup", unit_id=unit_id, amount=int(amount), parent_id=parent_id)
        )

    def spends(self) -> list[_Spend]:
        return [row for row in self._rows if row.kind == "leaf"]

    def as_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "kind": row.kind,
                "unit_id": row.unit_id,
                "amount": row.amount,
                "parent_id": row.parent_id,
            }
            for row in self._rows
        ]

    def leaf_total(self) -> int:
        return sum(row.amount for row in self._rows if row.kind == "leaf")

    def rollup_total(self) -> int:
        return sum(row.amount for row in self._rows if row.kind == "rollup")

    def naive_sum_all_rows(self) -> int:
        return sum(row.amount for row in self._rows)


@dataclass
class ExecuteResult:
    receipts: dict[str, dict[str, Any]]
    artifact_spaces: dict[str, str]
    artifacts: dict[str, str]
    child_budgets: dict[str, int]
    parent_budget: int
    ledger: SpendLedger

    def rollup_assertion(self) -> dict[str, Any]:
        leaf = self.ledger.leaf_total()
        naive = self.ledger.naive_sum_all_rows()
        child_sum = sum(self.child_budgets.values())
        return {
            "exact": self.parent_budget == child_sum == leaf
            or (
                self.parent_budget == child_sum
                and self.parent_budget == leaf
            ),
            "rollup_matches": self.parent_budget == child_sum,
            "naive_would_double_count": naive > leaf,
            "parent_spend_total": self.parent_budget,
            "child_sum": child_sum,
            "leaf_spend_count": len(self.ledger.spends()),
            "rollup_count": sum(1 for r in self.ledger.as_rows() if r["kind"] == "rollup"),
            "naive_including_rollups": naive,
            "leaf_total": leaf,
        }


def _receipt_id(namespace: str, node_id: str, namespacing: bool) -> str:
    if namespacing and namespace:
        return f"{namespace}::{node_id}"
    return node_id


def _space_for(root: Path, namespace: str, namespacing: bool) -> Path:
    if namespacing and namespace:
        return root / namespace
    return root / "_shared"


def execute(
    workflow: Workflow,
    registry: dict[str, Workflow],
    artifacts_root: str | Path,
    params: dict[str, Any] | None = None,
    parent_perms: Iterable[str] | None = None,
    opts: ExecuteOpts | None = None,
    **kwargs: Any,
) -> ExecuteResult:
    """Run ``workflow``, writing artifacts only under ``artifacts_root``."""
    opts = opts or ExecuteOpts()
    if kwargs.get("opts") is not None and opts is not None:
        pass
    root = Path(artifacts_root)
    root.mkdir(parents=True, exist_ok=True)
    params = dict(params or {})
    enforce = parent_perms is not None
    perms: frozenset[str] | None = (
        freeze_tool_permissions(parent_perms) if enforce else None
    )
    receipts: dict[str, dict[str, Any]] = {}
    artifact_spaces: dict[str, str] = {}
    artifacts: dict[str, str] = {}
    child_budgets: dict[str, int] = {}
    ledger = SpendLedger()

    def run_wf(
        wf: Workflow,
        namespace: str,
        current_perms: frozenset[str] | None,
        current_params: dict[str, Any],
        depth: int,
        parent_ns: str | None,
    ) -> int:
        spent = 0
        for node in wf.nodes:
            if isinstance(node, Subworkflow):
                child_ns = node.id_namespace or (
                    f"{namespace}.{node.id}" if namespace else node.id
                )
                declared = freeze_tool_permissions(node.tool_permissions)
                if current_perms is None:
                    child_perms: frozenset[str] | None = None
                    effective_list = sorted(declared) if declared else []
                else:
                    if declared:
                        child_perms = narrow(current_perms, declared)
                    else:
                        child_perms = current_perms
                    effective_list = sorted(child_perms)
                rec_id = child_ns if opts.namespacing else node.id
                receipts[rec_id] = {
                    "id": rec_id,
                    "kind": "subworkflow",
                    "effective_permissions": effective_list,
                    "declared": sorted(declared),
                    "parent": sorted(current_perms or ()),
                    "depth": depth,
                    "namespace": child_ns,
                }
                space = _space_for(root, child_ns, opts.namespacing)
                space.mkdir(parents=True, exist_ok=True)
                artifact_spaces[child_ns] = str(space)
                child_wf = registry[node.workflow_ref]
                child_params = dict(current_params)
                child_params.update(node.param_bindings or {})
                child_spend = run_wf(
                    child_wf,
                    child_ns,
                    child_perms,
                    child_params,
                    depth + 1,
                    child_ns,
                )
                child_budgets[child_ns] = child_spend
                ledger.add_rollup(child_ns, child_spend, parent_id=parent_ns)
                spent += child_spend
            elif isinstance(node, Task):
                rid = _receipt_id(namespace, node.id, opts.namespacing)
                tool = node.attempted_tool
                effective_list = sorted(current_perms) if current_perms is not None else []
                if tool and current_perms is not None and tool not in current_perms:
                    raise ToolPermissionError(
                        f"tool {tool!r} not in effective {effective_list}",
                        code="tool-permission-denied",
                        tool=tool,
                    )
                space = _space_for(root, namespace, opts.namespacing)
                dest_dir = space / node.id
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / (node.write_name or "out.txt")
                payload = str(current_params.get(node.write_from_param, node.id))
                dest.write_text(payload, encoding="utf-8")
                artifacts[rid] = str(dest)
                receipts[rid] = {
                    "id": rid,
                    "kind": "task",
                    "payload": payload,
                    "effective_permissions": effective_list,
                    "attempted_tool": tool,
                    "depth": depth,
                    "path": str(dest),
                }
                amount = int(node.budget)
                ledger.add_leaf(rid, amount, parent_id=namespace or parent_ns)
                spent += amount
            else:
                raise TypeError(f"unknown node type {type(node)!r}")
        return spent

    parent_spend = run_wf(workflow, "", perms, params, 0, None)
    if opts.count_rollups_as_spend:
        parent_budget = ledger.naive_sum_all_rows()
    else:
        parent_budget = ledger.leaf_total()
    if not child_budgets and parent_spend:
        child_budgets[workflow.id] = parent_spend
    return ExecuteResult(
        receipts=receipts,
        artifact_spaces=artifact_spaces,
        artifacts=artifacts,
        child_budgets=child_budgets,
        parent_budget=parent_budget,
        ledger=ledger,
    )


__all__ = [
    "ExecuteOpts",
    "ExecuteResult",
    "SpendLedger",
    "Subworkflow",
    "Task",
    "Workflow",
    "execute",
]
