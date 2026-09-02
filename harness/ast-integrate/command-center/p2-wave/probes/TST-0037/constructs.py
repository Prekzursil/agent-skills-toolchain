"""Frozen TST-0037 construct set.

The catalog question names seven workflow-DSL constructs. Near-neighbours
(repair-loop, dispatch retry.py, Pipeline) are recorded as residual, never
substituted for the named construct.
"""
from __future__ import annotations

QUESTION = (
    "Does every construct the workflow DSL documents (fan-out, barrier, "
    "loop-with-convergence, human checkpoint, subworkflow, retry, resume) "
    "have a schema rule AND a conformance case, and which documented "
    "construct has no validator at all?"
)

CONSTRUCTS: tuple[dict, ...] = (
    {
        "id": "fan-out",
        "production_types": frozenset({"fanout", "fan-out"}),
        "spec_classes": frozenset({"FanOut", "DynamicFanOut"}),
        "violation_ids": frozenset(
            {"fanout-empty", "fanout-unknown-member", "fanout-unit-unknown"}
        ),
        "contract_rules": ("fanout-empty", "fanout-unknown-member"),
    },
    {
        "id": "barrier",
        "production_types": frozenset({"barrier"}),
        "spec_classes": frozenset({"Barrier"}),
        "violation_ids": frozenset(
            {"barrier-empty-awaits", "barrier-empty", "barrier-awaits-unknown"}
        ),
        "contract_rules": ("barrier-empty-awaits", "barrier-awaits-unknown"),
    },
    {
        "id": "loop-with-convergence",
        "production_types": frozenset({"loop", "loop-with-convergence"}),
        "spec_classes": frozenset({"Loop"}),
        "violation_ids": frozenset({"loop-unbounded"}),
        "contract_rules": ("loop-unbounded",),
        "not_this": "repair-loop is a fix-review cycle (IMP-0139), not loop-with-convergence (IMP-0130)",
    },
    {
        "id": "human-checkpoint",
        "production_types": frozenset({"human-checkpoint", "checkpoint"}),
        "spec_classes": frozenset({"HumanCheckpoint"}),
        "violation_ids": frozenset({"checkpoint-missing-prompt"}),
        "contract_rules": ("checkpoint-missing-prompt",),
    },
    {
        "id": "subworkflow",
        "production_types": frozenset({"subworkflow"}),
        "spec_classes": frozenset({"Subworkflow"}),
        "violation_ids": frozenset({"subworkflow-cycle", "subworkflow-unknown-ref"}),
        "contract_rules": ("subworkflow-cycle",),
    },
    {
        "id": "retry",
        "production_types": frozenset({"retry"}),
        "spec_classes": frozenset({"Retry"}),
        "violation_ids": frozenset({"retry-unbounded"}),
        "contract_rules": ("retry-unbounded",),
        "not_this": "tools/agentspec/agentspec/retry.py is dispatch-layer RetryPlan, not a DSL node",
    },
    {
        "id": "resume",
        "production_types": frozenset({"resume"}),
        "spec_classes": frozenset({"Resume"}),
        "violation_ids": frozenset({"resume-missing-token"}),
        "contract_rules": ("resume-missing-token",),
    },
)

BY_ID = {row["id"]: row for row in CONSTRUCTS}
ORDER = tuple(row["id"] for row in CONSTRUCTS)

TYPE_ALIASES = {
    "fanout": "fan-out",
    "fan-out": "fan-out",
    "barrier": "barrier",
    "loop": "loop-with-convergence",
    "loop-with-convergence": "loop-with-convergence",
    "human-checkpoint": "human-checkpoint",
    "checkpoint": "human-checkpoint",
    "subworkflow": "subworkflow",
    "retry": "retry",
    "resume": "resume",
    "unit": "unit",
    "pipeline": "pipeline",
    "repair-loop": "repair-loop",
}


def canonical_type(raw: object) -> str:
    if not isinstance(raw, str):
        return ""
    return TYPE_ALIASES.get(raw, raw)
