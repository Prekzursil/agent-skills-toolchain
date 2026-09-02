"""Shared PCJ fixture for IMP-0283 probes.

Plants a proposer identity token and a private-reasoning token that the
critique does not surface. The judge-view census must contain neither.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.topology.pcj import (  # noqa: E402
    Claim,
    Critique,
    CritiquePoint,
    Proposal,
    judge_view,
    run_pipeline,
)

UNIT = "IMP-0283"
PROPOSER_ID = "seat:proposer:ALICE-IDENTITY-TOKEN-QK7"
CRITIC_ID = "seat:critic:BOB"
JUDGE_ID = "seat:judge:CAROL"
UNSURFACED = "PRIVATE-REASONING-NEVER-SURFACED-ZX9-WOLF"
SURFACED = "latency is dominated by sequential disk reads"
FABRICATED_POINT_ID = "CP-FABRICATED-DOES-NOT-EXIST"
QUESTION = "Should the cache be sharded across four nodes before the next load test?"


def make_proposal() -> Proposal:
    return Proposal(
        proposal_id="prop-cache-shard-1",
        proposer_id=PROPOSER_ID,
        question=QUESTION,
        claims=(
            Claim(
                claim_id="CLM-1",
                text="Sharding the cache across four nodes will cut p99 latency in half.",
            ),
            Claim(
                claim_id="CLM-2",
                text="The current replica set is already write-safe under the projected peak.",
            ),
        ),
        reasoning=(
            f"{UNSURFACED} The proposer privately believes the win comes from "
            "avoiding a lock they have not measured, not from shard count."
        ),
        aliases=("Alice-QK7",),
    )


def make_critique(proposal: Proposal) -> Critique:
    # Surfaces disk-read latency. Does not copy proposer id or UNSURFACED token.
    return Critique(
        critique_id="crit-cache-shard-1",
        critic_id=CRITIC_ID,
        proposal_id=proposal.proposal_id,
        points=(
            CritiquePoint(
                point_id="CP-1",
                claim_id="CLM-1",
                text=f"{SURFACED}; shard count without a lock profile does not imply p99 halves.",
                polarity="object",
            ),
            CritiquePoint(
                point_id="CP-2",
                claim_id="CLM-2",
                text="Write-safety is asserted without a peak-load write-amp measurement.",
                polarity="question",
            ),
        ),
    )


def make_view():
    proposal = make_proposal()
    critique = make_critique(proposal)
    return proposal, critique, judge_view(proposal, critique)


def rule_from_view(view):
    point_ids = [p["point_id"] for p in view["points"]]
    return {
        "ruling_id": "rul-cache-shard-1",
        "judge_id": JUDGE_ID,
        "verdict": "reject",
        "citations": point_ids[:1],
        "rationale": "CP-1 is unresolved empirically; do not shard on an unmeasured lock story.",
    }


def live_pipeline():
    return run_pipeline(
        propose=make_proposal,
        critique=make_critique,
        rule=rule_from_view,
    )
