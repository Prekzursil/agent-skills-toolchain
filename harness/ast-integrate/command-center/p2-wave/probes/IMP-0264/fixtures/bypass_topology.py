"""Planted direct-write bypass topology (negative control). Not used in production."""

from __future__ import annotations

from collections.abc import Sequence


class BypassTopology:
    """Writes participant output and the event log, skipping the kernel."""

    def plan_round(
        self,
        round_index: int,
        roster: Sequence[str],
        *,
        timeout_ms: int = 0,
        max_chars: int = 0,
        obligations: Sequence[str] = (),
        events=None,
    ):
        for pid in roster:
            participant = type("Participant", (), {})()
            participant.output = f"bypass:{pid}"
        if events is None:
            events = []
        events.append({"kind": "TURN", "bypass": True, "round": round_index})
        outputs = {}
        outputs["all"] = "direct-write"
        return None
