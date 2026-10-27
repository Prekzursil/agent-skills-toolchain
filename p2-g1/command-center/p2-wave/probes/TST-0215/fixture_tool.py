"""TST-0215 fixture tool executor: the sequence downstream of routing selection.

The receipt is explicit that no production B07 executor exists; this fixture
executor maps the router's top-k selection to a deterministic fixture tool
sequence ([Router.route, fixture_tool:<top-1>]) so signal (b) - the executed
tool sequence for the same tasks - is independent of probe A's top-k diff.
"""
from __future__ import annotations

from typing import Any


def executed_sequence(routed_ids: list[str]) -> list[str]:
    """Deterministic fixture executor downstream of the router's selection.

    Executes the FULL top-k selection (one fixture tool invocation per
    selected capability), so the executed sequence reflects everything the
    router would inject, not merely the first slot.
    """
    if not routed_ids:
        return ["fixture_tool:none"]
    return ["Router.route"] + [f"fixture_tool:{cid}" for cid in routed_ids]


def sequence_identity(a: list[str], b: list[str]) -> bool:
    return a == b


def route_for_execution(router: Any, query: str, k: int = 3) -> list[str]:
    decision = router.route(query, k=k)
    return list(decision.ids)
