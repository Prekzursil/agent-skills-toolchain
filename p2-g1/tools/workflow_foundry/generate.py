"""Generate workflows from traces and from taxonomy gaps (IMP-0194)."""
from __future__ import annotations

from typing import Any

from workflow_foundry.gap_finder import Taxonomy


def from_trace(log: dict[str, Any]) -> dict[str, Any]:
    stages = []
    tools = []
    for event in log.get("events") or []:
        stages.append(
            {
                "id": event["stage_id"],
                "tool": event["tool"],
                "args": list(event["args"]),
                "output": event["output"],
            }
        )
        tools.append(event["tool"])
    return {
        "id": f"wf-from-{log.get('trace_id')}",
        "tools": tools,
        "stages": stages,
        "stop_rule": {"max_stages": len(stages)},
    }


def from_gap(gap: str, tax: Taxonomy) -> dict[str, Any]:
    return {
        "id": f"wf-gap-{gap.replace(':', '-').replace(' ', '')}",
        "covers": [gap],
        "category": gap.split(":", 1)[0] if ":" in gap else gap,
        "stages": [{"id": "cover", "tool": "cover", "args": [gap], "output": "covered"}],
        "stop_rule": {"max_stages": 1},
        "tools": ["cover"],
    }


def as_candidate(workflow: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": workflow.get("id"),
        "covers": list(workflow.get("covers") or []),
        "category": workflow.get("category"),
        "workflow": workflow,
    }
