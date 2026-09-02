"""Shared exact-tie fixture and census policies for IMP-0354 probes."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.vote.tiebreak import (  # noqa: E402
    BallotOption,
    Member,
    Policy,
    TieCase,
)

RECORDED_SEED = "imp-0354-recorded-seed-v1"
QUESTION_ID = "imp-0354-exact-tie-fixture"


def exact_tie_fixture() -> TieCase:
    """2-2 split. Chair and seniority pick different sides, so the declared
    rule is load-bearing rather than an implicit listing order.
    """
    return TieCase(
        question_id=QUESTION_ID,
        options=(
            BallotOption(option_id="alpha", votes=2),
            BallotOption(option_id="beta", votes=2),
        ),
        members=(
            Member(
                member_id="chair-c",
                role="chair",
                seniority=10,
                ballot="alpha",
            ),
            Member(
                member_id="senior-s",
                role="member",
                seniority=50,
                ballot="beta",
            ),
            Member(
                member_id="m1",
                role="member",
                seniority=5,
                ballot="alpha",
            ),
            Member(
                member_id="m2",
                role="member",
                seniority=5,
                ballot="beta",
            ),
        ),
    )


def census_policies() -> dict[str, Policy]:
    return {
        "chair-casting-vote": Policy(
            rule="chair-casting-vote", policy_id="census-chair"
        ),
        "seniority": Policy(rule="seniority", policy_id="census-seniority"),
        "recorded-seed-coin-flip": Policy(
            rule="recorded-seed-coin-flip",
            seed=RECORDED_SEED,
            policy_id="census-coin",
        ),
        "escalation": Policy(rule="escalation", policy_id="census-escalation"),
        "no-decision": Policy(rule="no-decision", policy_id="census-none"),
    }


def coin_flip_policy(seed: str | None = RECORDED_SEED) -> Policy:
    return Policy(
        rule="recorded-seed-coin-flip",
        seed=seed,
        policy_id="coin-recorded",
    )
