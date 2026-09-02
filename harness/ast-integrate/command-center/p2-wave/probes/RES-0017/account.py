"""Occupancy vs cumulative: the estate already burned a restart on this mix-up.

Occupancy numerator is turn-0 injected tokens (the snapshot that fills the
window). tokens_cumulative is a different ledger field and is never the
occupancy numerator.
"""
from __future__ import annotations

OCCUPANCY_FIELD = "turn0_injected_tokens"
CUMULATIVE_FIELD = "tokens_cumulative"
LAST_TURN_FIELD = "tokens_last_turn"
ACCOUNTING_SOURCE = (
    "res0017.hermetic.BPE.count(concatenated-turn0-injection)@"
    "command-center/p2-wave/probes/RES-0017/bpe.py"
)


def occupancy_from_turn0(turn0_tokens: int) -> int:
    return int(turn0_tokens)


def simulate_later_turns(turn0_tokens: int, extra_turn_tokens: list[int]) -> dict:
    """Cumulative grows; occupancy numerator stays the turn-0 snapshot."""
    cumulative = int(turn0_tokens)
    last = int(turn0_tokens)
    turns = [
        {
            "id": "turn-0",
            "tokens_this_turn": last,
            "tokens_cumulative_after": cumulative,
            "occupancy_numerator": occupancy_from_turn0(turn0_tokens),
        }
    ]
    for i, n in enumerate(extra_turn_tokens, start=1):
        last = int(n)
        cumulative += last
        turns.append(
            {
                "id": f"turn-{i}",
                "tokens_this_turn": last,
                "tokens_cumulative_after": cumulative,
                "occupancy_numerator": occupancy_from_turn0(turn0_tokens),
            }
        )
    return {
        OCCUPANCY_FIELD: occupancy_from_turn0(turn0_tokens),
        CUMULATIVE_FIELD: cumulative,
        LAST_TURN_FIELD: last,
        "turns": turns,
        "cumulative_equals_occupancy": cumulative == occupancy_from_turn0(turn0_tokens),
        "cumulative_rejected_as_occupancy": True,
        "occupancy_field": OCCUPANCY_FIELD,
        "cumulative_field": CUMULATIVE_FIELD,
        "last_turn_field": LAST_TURN_FIELD,
        "accounting_source": ACCOUNTING_SOURCE,
    }
