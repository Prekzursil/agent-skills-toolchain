"""IMP-0146 fixture constructors: every existing and Phase-7 node type."""

from __future__ import annotations

import sys
from pathlib import Path

_AGENTSPEC = Path(__file__).resolve().parents[4] / "tools" / "agentspec"
if str(_AGENTSPEC) not in sys.path:
    sys.path.insert(0, str(_AGENTSPEC))

from agentspec.spec import (  # noqa: E402
    EXISTING_NODE_KINDS,
    NEW_NODE_KINDS,
    Barrier,
    DynamicFanOut,
    FanOut,
    HumanCheckpoint,
    Loop,
    Param,
    ParamBinding,
    Pipeline,
    Routing,
    Subworkflow,
    WorkUnit,
    Workflow,
)

ROUTING = Routing(
    vendor="anthropic",
    model="opus",
    role="implementer",
    fallbacks=("sonnet",),
)


def _unit(uid: str, prompt: str) -> WorkUnit:
    return WorkUnit(
        id=uid,
        prompt_ref=prompt,
        routing=ROUTING,
        tool_permissions=("Read", "Grep"),
        source_policy=("code", "official-docs"),
        on_failure="abort",
    )


def workflow_fanout() -> Workflow:
    return Workflow(
        id="wf.fanout",
        spec_version="7.0",
        units=(_unit("u.scan", "scan.md"), _unit("u.a", "a.md"), _unit("u.b", "b.md")),
        nodes=(FanOut(id="n.fan", unit_ids=("u.a", "u.b"), on_failure="continue"),),
        params=(),
    )


def workflow_barrier() -> Workflow:
    return Workflow(
        id="wf.barrier",
        spec_version="7.0",
        units=(_unit("u.left", "left.md"), _unit("u.right", "right.md")),
        nodes=(Barrier(id="n.bar", wait_for=("u.left", "u.right")),),
    )


def workflow_pipeline() -> Workflow:
    return Workflow(
        id="wf.pipeline",
        spec_version="7.0",
        units=(_unit("u.s1", "s1.md"), _unit("u.s2", "s2.md"), _unit("u.s3", "s3.md")),
        nodes=(Pipeline(id="n.pipe", stages=("u.s1", "u.s2", "u.s3")),),
    )


def workflow_subworkflow() -> Workflow:
    return Workflow(
        id="wf.sub",
        spec_version="7.0",
        units=(_unit("u.outer", "outer.md"),),
        nodes=(
            Subworkflow(
                id="n.sub",
                workflow_ref="wf.inner",
                param_bindings=(ParamBinding(name="region", value="eu"),),
                id_namespace="inner.",
            ),
        ),
        params=(
            Param(
                name="region",
                param_type="string",
                required=True,
                enum=("eu", "us"),
            ),
        ),
    )


def workflow_loop() -> Workflow:
    return Workflow(
        id="wf.loop",
        spec_version="7.0",
        units=(_unit("u.body", "body.md"),),
        nodes=(
            Loop(
                id="n.loop",
                body=("u.body",),
                convergence_expr="delta < 0.01",
                max_iterations=8,
                on_bound_reached="abort",
            ),
        ),
    )


def workflow_checkpoint() -> Workflow:
    return Workflow(
        id="wf.checkpoint",
        spec_version="7.0",
        units=(_unit("u.after", "after.md"),),
        nodes=(
            HumanCheckpoint(
                id="n.gate",
                prompt_ref="approve.md",
                allowed_responses=("approve", "reject"),
                default_if_unanswered="reject",
                pause_token="pause.gate.v1",
            ),
        ),
    )


def workflow_dynamic_fanout() -> Workflow:
    return Workflow(
        id="wf.dynfan",
        spec_version="7.0",
        units=(_unit("u.producer", "producer.md"),),
        nodes=(
            DynamicFanOut(
                id="n.dyn",
                producer_unit="u.producer",
                item_path="$.items[*]",
                unit_template="u.item",
                max_cardinality=32,
            ),
        ),
    )


def workflow_all_kinds() -> Workflow:
    """One workflow that carries every node type canonical.py must round-trip."""
    return Workflow(
        id="wf.all-kinds",
        spec_version="7.0",
        units=(
            _unit("u.scan", "scan.md"),
            _unit("u.a", "a.md"),
            _unit("u.b", "b.md"),
            _unit("u.body", "body.md"),
            _unit("u.producer", "producer.md"),
        ),
        nodes=(
            FanOut(id="n.fan", unit_ids=("u.a", "u.b")),
            Barrier(id="n.bar", wait_for=("u.a", "u.b")),
            Pipeline(id="n.pipe", stages=("u.scan", "u.a")),
            Subworkflow(
                id="n.sub",
                workflow_ref="wf.inner",
                param_bindings=(ParamBinding(name="k", value="v"),),
                id_namespace="ns.",
            ),
            Loop(
                id="n.loop",
                body=("u.body",),
                convergence_expr="done",
                max_iterations=3,
                on_bound_reached="abort",
            ),
            HumanCheckpoint(
                id="n.gate",
                prompt_ref="gate.md",
                allowed_responses=("yes", "no"),
                default_if_unanswered="no",
                pause_token="tok.1",
            ),
            DynamicFanOut(
                id="n.dyn",
                producer_unit="u.producer",
                item_path="$.xs",
                unit_template="u.item",
                max_cardinality=7,
            ),
        ),
        params=(
            Param(
                name="token",
                param_type="secret_ref",
                required=True,
                secret_ref="env:WORKFLOW_TOKEN",
            ),
        ),
    )


FIXTURES: dict[str, Workflow] = {
    "fanout": workflow_fanout(),
    "barrier": workflow_barrier(),
    "pipeline": workflow_pipeline(),
    "subworkflow": workflow_subworkflow(),
    "loop": workflow_loop(),
    "human-checkpoint": workflow_checkpoint(),
    "dynamic-fanout": workflow_dynamic_fanout(),
    "all-kinds": workflow_all_kinds(),
}


def kinds_in(workflow: Workflow) -> set[str]:
    found = {u.kind for u in workflow.units}
    for node in workflow.nodes:
        found.add(getattr(node, "kind"))
    return found


def required_kinds() -> frozenset[str]:
    return EXISTING_NODE_KINDS | NEW_NODE_KINDS
