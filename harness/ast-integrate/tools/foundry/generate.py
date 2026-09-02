"""Generate a workflow from a typed goal, returning incumbents when covered."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from foundry.constants import NAMED_FAILURE_11331
from foundry.scout import load_library


@dataclass
class Scout:
    verdict: str


@dataclass
class Generation:
    action: str
    rebuilt: bool
    workflow: dict | None
    named_failure_avoided: str | None = None
    scout: Scout = field(default_factory=lambda: Scout("BUILD"))


def generate_from_goal(goal: dict, gate: bool = True) -> Generation:
    library = load_library()
    text = str(goal.get("text") or "")
    if not gate:
        return Generation(
            action="BUILD",
            rebuilt=True,
            workflow={
                "id": "wf.generated.mutant-rebuild",
                "goal": text,
                "kind": "generated",
                "generated": True,
            },
            scout=Scout("BUILD"),
        )
    for row in library:
        needle = str(row.get("goal") or "")
        if needle and needle in text:
            return Generation(
                action="REFUSE",
                rebuilt=False,
                workflow=row,
                named_failure_avoided=NAMED_FAILURE_11331,
                scout=Scout("ADOPT"),
            )
    return Generation(
        action="BUILD",
        rebuilt=True,
        workflow={
            "id": "wf.generated." + str(goal.get("id") or "anon"),
            "goal": text,
            "kind": "generated",
            "generated": True,
        },
        scout=Scout("BUILD"),
    )


__all__ = ["Generation", "Scout", "generate_from_goal"]
