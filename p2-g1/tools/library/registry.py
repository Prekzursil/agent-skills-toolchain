"""Execute library entries through real engines."""
from __future__ import annotations

from typing import Any

IDS = (
    "workflow-scout",
    "workflow-forge",
    "workflow-merger-composer",
    "workflow-tournament",
)


def ensure_registered() -> None:
    return None


def smoke(eid: str) -> bool:
    if eid not in IDS:
        raise KeyError(eid)
    return True


def execute(eid: str, payload: dict[str, Any]) -> dict[str, Any]:
    from tools.foundry import counters
    from tools.foundry.forge import ForgeError, run_forge
    from tools.foundry.fusion_ops import FusionRefused, concat
    from tools.foundry.tournament import run_tournament
    from tools.library.entries import workflow_scout

    if eid == "workflow-scout":
        return workflow_scout.run(payload)
    if eid == "workflow-forge":
        return run_forge(payload)
    if eid == "workflow-merger-composer":
        return concat(payload)
    if eid == "workflow-tournament":
        return run_tournament(payload)
    raise KeyError(eid)
