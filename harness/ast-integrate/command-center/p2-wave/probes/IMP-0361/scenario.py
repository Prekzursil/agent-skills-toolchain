"""Hermetic five-seat recusal fixture for IMP-0361."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.integrity.recusal import (  # noqa: E402
    RECUSED_BALLOT_IN_TALLY,
    Ballot,
    Conflict,
    Contribution,
    RecusalSession,
    Seat,
)

RECUSED = "seat-A"
REPLACEMENT = "seat-F"
ARTIFACT = "proposal-1"
ROUND = 1


def roster() -> list[Seat]:
    return [
        Seat(id="seat-A", vendor="anthropic", authored_artifact=True),
        Seat(id="seat-B", vendor="openai"),
        Seat(id="seat-C", vendor="google"),
        Seat(id="seat-D", vendor="meta"),
        Seat(id="seat-E", vendor="mistral"),
    ]


def votes() -> list[tuple[str, str]]:
    return [
        ("seat-A", "approve"),
        ("seat-B", "approve"),
        ("seat-C", "approve"),
        ("seat-D", "reject"),
        ("seat-E", "reject"),
    ]


def seated_and_voted() -> RecusalSession:
    session = RecusalSession(seats=roster(), quorum_ratio=0.6)
    session.add_contribution(
        Contribution(
            id="idea-A1",
            seat_id="seat-A",
            kind="idea",
            body="Ship the proposal with the original scope.",
            round_id=ROUND,
        )
    )
    session.add_contribution(
        Contribution(
            id="idea-B1",
            seat_id="seat-B",
            kind="idea",
            body="Narrow the proposal to the measured subset.",
            round_id=ROUND,
        )
    )
    for seat_id, choice in votes():
        session.cast_ballot(
            Ballot(
                ballot_id=f"b-{seat_id}-r{ROUND}",
                seat_id=seat_id,
                choice=choice,
                round_id=ROUND,
            )
        )
    return session


def declare_recuse_replace() -> dict:
    session = seated_and_voted()
    pre_census = session.contribution_census()
    pre_quorum = session.recompute_quorum()
    pre_tally = session.recompute_tally()
    session.declare(
        RECUSED,
        Conflict(kind="authored_artifact", target=ARTIFACT, note="author seated as judge"),
    )
    recusal = session.recuse(RECUSED, reason="authored the artifact under review")
    comparison = session.compare_tallies()
    census = session.census_retained(pre_census, RECUSED)
    post_quorum = session.recompute_quorum()
    honest_audit = session.audit_counting_ballots(session.counting_ballots())
    recorded_audit = session.audit_counting_ballots(session.recorded_ballots())
    replacement = session.replace(
        RECUSED,
        Seat(id=REPLACEMENT, vendor="cohere"),
    )
    after_replace_quorum = session.recompute_quorum()
    inherited = session.replacement_ballot_count(REPLACEMENT)
    recused_still_counts = RECUSED in comparison.recomputed.counting_seat_ids
    return {
        "recused_seat": RECUSED,
        "replacement_seat": REPLACEMENT,
        "pre_decision": pre_tally.decision,
        "pre_counts": dict(pre_tally.counts),
        "pre_quorum": pre_quorum.to_dict(),
        "recusal_declared": recusal.declared,
        "excluded_ballot_ids": list(recusal.excluded_ballot_ids),
        "retained_contribution_ids": list(recusal.retained_contribution_ids),
        "comparison": comparison.to_dict(),
        "differ": comparison.differ,
        "recused_in_recorded": comparison.recused_in_recorded,
        "recused_in_recomputed": comparison.recused_in_recomputed,
        "recused_still_counts": recused_still_counts,
        "recomputed_decision": comparison.recomputed.decision,
        "recomputed_counts": dict(comparison.recomputed.counts),
        "recorded_decision": comparison.recorded.decision,
        "recorded_counts": dict(comparison.recorded.counts),
        "census": census,
        "census_retained": census["retained"],
        "post_quorum": post_quorum.to_dict(),
        "honest_audit": honest_audit.to_dict(),
        "recorded_audit": recorded_audit.to_dict(),
        "inherited_ballots": inherited,
        "replace_inherited_ballots": replacement.inherited_ballots,
        "after_replace_quorum": after_replace_quorum.to_dict(),
        "contribution_hashes_pre": dict(pre_census.hashes_by_id),
        "contribution_hashes_post": dict(session.contribution_census().hashes_by_id),
    }


def quorum_void_then_restore() -> dict:
    session = seated_and_voted()
    session.declare(
        "seat-A", Conflict(kind="authored_artifact", target=ARTIFACT)
    )
    session.recuse("seat-A", reason="authored the artifact under review")
    session.recuse("seat-D", reason="quota breach")
    session.recuse("seat-E", reason="inactivity")
    void_q = session.recompute_quorum()
    void_tally = session.recompute_tally()
    session.replace("seat-D", Seat(id="seat-G", vendor="xai"))
    restored_q = session.recompute_quorum()
    restored_tally = session.recompute_tally()
    return {
        "void_eligible_n": void_q.eligible_n,
        "void_required": void_q.required,
        "void": void_q.void,
        "void_reason": void_tally.void_reason,
        "void_decision": void_tally.decision,
        "restored_eligible_n": restored_q.eligible_n,
        "restored_met": restored_q.met,
        "restored_void": restored_q.void,
        "restored_decision": restored_tally.decision,
        "restored_counts": dict(restored_tally.counts),
    }


def negative_control() -> dict:
    session = seated_and_voted()
    session.declare(
        RECUSED, Conflict(kind="authored_artifact", target=ARTIFACT)
    )
    session.recuse(RECUSED, reason="authored the artifact under review")
    honest = session.audit_counting_ballots(session.counting_ballots())
    planted = session.audit_counting_ballots(session.recorded_ballots())
    comparison = session.compare_tallies()
    return {
        "code": RECUSED_BALLOT_IN_TALLY,
        "honest_fired": honest.fired,
        "honest_code": honest.code,
        "planted_fired": planted.fired,
        "planted_code": planted.code,
        "planted_leaked_seats": list(planted.leaked_seat_ids),
        "planted_leaked_ballots": list(planted.leaked_ballot_ids),
        "recused_in_recomputed": comparison.recused_in_recomputed,
        "recused_in_recorded": comparison.recused_in_recorded,
        "differ": comparison.differ,
        "both_states": (not honest.fired) and planted.fired,
    }


def deepcopy_session(session: RecusalSession) -> RecusalSession:
    return copy.deepcopy(session)
