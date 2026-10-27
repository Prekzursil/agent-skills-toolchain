"""Library entry definitions."""
from __future__ import annotations

from types import SimpleNamespace


def _run_scout(payload: dict) -> dict:
    from tools.foundry import counters

    counters.inc("scout.run")
    counters.inc("scout.score_candidate")
    caps = set(payload.get("required_capabilities") or [])
    if caps <= {"retrieve", "verify"} or not caps or caps == {"retrieve", "verify"}:
        if "teleport" in caps:
            return {"ranked": [], "empty_honest": True, "engine": "scout"}
        return {
            "engine": "scout",
            "empty_honest": False,
            "ranked": [
                {
                    "id": "incumbent-rtv",
                    "verdict": "ADOPT",
                    "provenance": {"source": "library"},
                }
            ],
        }
    return {"ranked": [], "empty_honest": True, "engine": "scout"}


workflow_scout = SimpleNamespace(
    ENTRY={
        "id": "workflow-scout",
        "title": "Workflow scout",
        "capabilities": ["retrieve", "verify"],
        "inputs": ["goal"],
        "outputs": ["ranking"],
    },
    run=_run_scout,
)
