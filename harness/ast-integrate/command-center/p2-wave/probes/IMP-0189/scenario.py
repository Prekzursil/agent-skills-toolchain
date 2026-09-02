"""Shared two-level meta-workflow fixtures for IMP-0189 probes."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec import SPEC_VERSION  # noqa: E402
from agentspec.compose import ComposeResult, compose_and_run  # noqa: E402
from agentspec.spec import ReceiptSpec, Subworkflow, WorkUnit, Workflow  # noqa: E402

CHILD_A_BUDGET = 10 + 20
CHILD_B_BUDGET = 15
META_BUDGET = CHILD_A_BUDGET + CHILD_B_BUDGET  # 45; must equal ledger parent total

_RECEIPT = ReceiptSpec(fmt="json", required_fields=("status",))


def _unit(uid: str, budget: int, fail_family: str | None = None) -> WorkUnit:
    return WorkUnit(
        id=uid,
        prompt=f"run {uid}",
        timeout_s=60,
        receipt=_RECEIPT,
        budget=budget,
        fail_family=fail_family,
    )


def success_registry() -> dict[str, Workflow]:
    child_a = Workflow(
        id="child-a",
        spec_version=SPEC_VERSION,
        units=(_unit("u1", 10), _unit("u2", 20)),
        nodes=(),
        budget_micro=CHILD_A_BUDGET,
    )
    child_b = Workflow(
        id="child-b",
        spec_version=SPEC_VERSION,
        units=(_unit("u1", 15),),
        nodes=(),
        budget_micro=CHILD_B_BUDGET,
    )
    meta = Workflow(
        id="meta",
        spec_version=SPEC_VERSION,
        units=(),
        nodes=(
            Subworkflow(id="embed-a", workflow_ref="child-a", id_namespace="embed-a"),
            Subworkflow(id="embed-b", workflow_ref="child-b", id_namespace="embed-b"),
        ),
        budget_micro=META_BUDGET,
    )
    return {"child-a": child_a, "child-b": child_b, "meta": meta}


def failing_child_registry() -> dict[str, Workflow]:
    child_a = Workflow(
        id="child-a",
        spec_version=SPEC_VERSION,
        units=(_unit("u1", 10, fail_family="timeout"),),
        nodes=(),
        budget_micro=10,
    )
    child_b = Workflow(
        id="child-b",
        spec_version=SPEC_VERSION,
        units=(_unit("u1", 15),),
        nodes=(),
        budget_micro=15,
    )
    meta = Workflow(
        id="meta",
        spec_version=SPEC_VERSION,
        units=(),
        nodes=(
            Subworkflow(id="embed-a", workflow_ref="child-a", id_namespace="embed-a"),
            Subworkflow(id="embed-b", workflow_ref="child-b", id_namespace="embed-b"),
        ),
        budget_micro=META_BUDGET,
        default_on_failure="continue",
    )
    return {"child-a": child_a, "child-b": child_b, "meta": meta}


def run_budget() -> ComposeResult:
    return compose_and_run(success_registry(), "meta")


def run_policy(action: str) -> ComposeResult:
    return compose_and_run(
        failing_child_registry(),
        "meta",
        policy_override={"timeout": action},
    )
