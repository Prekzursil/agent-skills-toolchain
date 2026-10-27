"""Round-robin council topology: roster order repeated for each round."""
from __future__ import annotations

from typing import Any, Iterable, Sequence


class RoundRobinTopology:
    def order(self, plan: Any) -> list[str]:
        roster = list(getattr(plan, "roster", ()) or ())
        n_rounds = int(getattr(plan, "n_rounds", 1) or 1)
        return roster * n_rounds

    def plan_round(
        self,
        round_index: int,
        roster: Sequence[str],
        *,
        timeout_ms: int = 0,
        max_chars: int = 0,
        obligations: Iterable[str] = (),
    ) -> tuple[int, tuple]:
        turns = tuple(
            (pid, tuple(obligations), timeout_ms, max_chars) for pid in roster
        )
        return (round_index, turns)
