"""Token and time accounting that keeps cumulative and last-turn separate.

Conflating the two is a measured past error (CNF-0081 tests_required). Cost
uses tokens_cumulative only. last_turn is recorded and must not be used as
the occupancy or cost numerator.
"""
from __future__ import annotations

from dataclasses import dataclass, field

USD_PER_TOKEN = 2e-6
RATE_SOURCE = (
    "cnf0081.hermetic.usd_per_token=2e-6 (synthetic fixture rate; not a vendor quote)"
)
CUMULATIVE_FIELD = "TokenLedger.tokens_cumulative"
LAST_TURN_FIELD = "TokenLedger.tokens_last_turn"
ACCOUNTING_SOURCE_MEASURED = (
    "cnf0081.hermetic.TokenLedger.tokens_cumulative@"
    "command-center/p2-wave/probes/CNF-0081/ledger.py"
)
ACCOUNTING_SOURCE_NO_RUN = "named:none-no-measured-run"
ACCOUNTING_SOURCE_ABSENT_ESTIMATOR = (
    "absent:tools/agentspec/agentspec/budget.py"
)


def cost_usd(tokens: int) -> float:
    return round(int(tokens) * USD_PER_TOKEN, 12)


@dataclass
class TokenLedger:
    turns: list[dict] = field(default_factory=list)
    tokens_cumulative: int = 0
    tokens_last_turn: int = 0

    def record_turn(self, tokens: int, stage_id: str) -> None:
        n = int(tokens)
        if n < 0:
            raise ValueError("token count must be >= 0")
        self.tokens_last_turn = n
        self.tokens_cumulative += n
        self.turns.append(
            {
                "stage_id": stage_id,
                "tokens_this_turn": n,
                "tokens_cumulative_after": self.tokens_cumulative,
            }
        )

    def snapshot(self) -> dict:
        return {
            "tokens_cumulative": self.tokens_cumulative,
            "tokens_last_turn": self.tokens_last_turn,
            "n_turns": len(self.turns),
            "turns": list(self.turns),
            "cost_usd_from_cumulative": cost_usd(self.tokens_cumulative),
            "cost_usd_from_last_turn_DO_NOT_USE": cost_usd(self.tokens_last_turn),
        }
