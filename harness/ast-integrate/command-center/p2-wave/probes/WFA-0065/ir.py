"""Closed IR kind set for WFA-0065.

Taken from the WFA-0044 catalog contract (the WorkflowIR spec artifact is
absent on this worktree). A transfer that needs any other kind is out of
scope, not silently adopted.
"""

from __future__ import annotations

IR_KINDS = frozenset(
    {
        "stage",
        "role",
        "gate",
        "tool_policy",
        "fan_out",
        "barrier",
        "loop",
        "convergence_rule",
        "human_checkpoint",
        "retry",
        "resume",
        "stopping_expression",
        "lineage",
    }
)

IR_SOURCE = {
    "unit_id": "WFA-0044",
    "artifact_path": "command-center/wfa/WFA-0044-workflow-ir-spec.json",
    "artifact_present": False,
    "catalog_anchor": "command-center/WORK-UNIT-CATALOG.json:WFA-0044.question_or_target",
    "kinds_sentence": (
        "stages, roles, gates, tool policy, fan-out and barriers, loops with "
        "convergence rules, human checkpoints, retries, resume, stopping "
        "expressions and lineage"
    ),
}
