"""Workflow-layer retries must not multiply dispatch attempts (IMP-0140)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentspec.retry import plan_retry


@dataclass
class WorkflowRetryPolicy:
    max_attempts: int = 3


@dataclass
class LayerDecision:
    layer: str
    retry: bool = False
    dispatch_plan: Any = None
    exhausted: bool = False


class DispatchLedger:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def record(self, layer: str, kind: str) -> None:
        self.events.append({"layer": layer, "kind": kind})

    def dispatch_attempt_count(self) -> int:
        return self.count("dispatch", "attempt")

    def count(self, layer: str, kind: str) -> int:
        return sum(1 for e in self.events if e.get("layer") == layer and e.get("kind") == kind)


def plan_workflow_retry(
    *,
    reason: str,
    workflow_failures: int,
    policy: WorkflowRetryPolicy,
    ledger: DispatchLedger,
    dispatch_failures: int = 0,
) -> LayerDecision:
    # Dispatch reasons call into plan_retry and count a dispatch attempt.
    from agentspec.retry import DISPATCH_RETRY_REASONS

    if reason in DISPATCH_RETRY_REASONS or reason in {"win-arg-limit", "rate-limited"}:
        plan = plan_retry(reason, attempt=max(1, dispatch_failures + 1))
        ledger.record("dispatch", "attempt")
        return LayerDecision(layer="dispatch", retry=plan.retry, dispatch_plan=plan)
    if workflow_failures + 1 >= policy.max_attempts:
        ledger.record("workflow", "attempt")
        return LayerDecision(layer="workflow", retry=False, exhausted=True)
    ledger.record("workflow", "attempt")
    return LayerDecision(layer="workflow", retry=True)


def exhaust_workflow_retries(
    reason: str, policy: WorkflowRetryPolicy, ledger: DispatchLedger
) -> dict[str, Any]:
    before = ledger.dispatch_attempt_count()
    last = None
    attempts = 0
    for i in range(policy.max_attempts):
        last = plan_workflow_retry(
            reason=reason,
            workflow_failures=i,
            policy=policy,
            ledger=ledger,
            dispatch_failures=0,
        )
        attempts += 1
        if last.exhausted or not last.retry:
            break
    return {
        "dispatch_before": before,
        "dispatch_after": ledger.dispatch_attempt_count(),
        "workflow_attempts": attempts,
        "last_exhausted": bool(last and (last.exhausted or attempts >= policy.max_attempts)),
        "last_layer": last.layer if last else "workflow",
    }


def rival_multiply_via_plan_retry(
    reason: str, policy: WorkflowRetryPolicy, ledger: DispatchLedger
) -> dict[str, Any]:
    before = ledger.dispatch_attempt_count()
    for _ in range(policy.max_attempts + 1):
        plan_retry(reason, attempt=1)
        ledger.record("dispatch", "attempt")
    return {
        "dispatch_before": before,
        "dispatch_after": ledger.dispatch_attempt_count(),
    }
