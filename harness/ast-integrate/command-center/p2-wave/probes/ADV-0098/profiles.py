"""Pinned honest / strategic / abstention profiles for ADV-0098."""
from __future__ import annotations

from engine import ballot

C3 = ("A", "B", "C")
C2 = ("A", "B")


def irv_compromise_honest():
    """Textbook IRV compromising (FairVote / Tideman teaching shape).

    5 A>B>C, 4 C>B>A, 2 B>C>A. Round 1 eliminates B; C wins 6-5.
    """
    return [
        ballot("a-bloc", ranking=("A", "B", "C"), weight=5),
        ballot("c-bloc", ranking=("C", "B", "A"), weight=4),
        ballot("b-bloc", ranking=("B", "C", "A"), weight=2),
    ], C3


def irv_compromise_strategic():
    """Two of five A-voters rank B first (compromise). B then wins."""
    return [
        ballot("a-honest", ranking=("A", "B", "C"), weight=3),
        ballot("a-strat", ranking=("B", "A", "C"), weight=2),
        ballot("c-bloc", ranking=("C", "B", "A"), weight=4),
        ballot("b-bloc", ranking=("B", "C", "A"), weight=2),
    ], C3


def irv_five_voter_honest():
    """Unweighted 5-voter IRV: 2 A>B>C, 1 B>A>C, 2 C>B>A. IRV elects A."""
    return [
        ballot("v0", ranking=("A", "B", "C")),
        ballot("v1", ranking=("A", "B", "C")),
        ballot("v2", ranking=("B", "A", "C")),
        ballot("v3", ranking=("C", "B", "A")),
        ballot("v4", ranking=("C", "B", "A")),
    ], C3


def irv_five_voter_strategic():
    """v3 (true C>B>A) reports B>A>C. IRV elects B, which v3 prefers to A."""
    return [
        ballot("v0", ranking=("A", "B", "C")),
        ballot("v1", ranking=("A", "B", "C")),
        ballot("v2", ranking=("B", "A", "C")),
        ballot("v3", ranking=("B", "A", "C")),
        ballot("v4", ranking=("C", "B", "A")),
    ], C3


def irv_noshow_honest():
    """IRV no-show: 5 A>B>C, 4 B>C>A, 3 C>A>B, 2 C>B>A. C wins."""
    return [
        ballot("a-bloc", ranking=("A", "B", "C"), weight=5),
        ballot("b-bloc", ranking=("B", "C", "A"), weight=4),
        ballot("c-a", ranking=("C", "A", "B"), weight=3),
        ballot("c-b", ranking=("C", "B", "A"), weight=2),
    ], C3


def irv_noshow_abstain():
    """Two A-voters abstain (a-bloc weight 3). B wins; A-voters prefer B>C."""
    return [
        ballot("a-bloc", ranking=("A", "B", "C"), weight=3),
        ballot("b-bloc", ranking=("B", "C", "A"), weight=4),
        ballot("c-a", ranking=("C", "A", "B"), weight=3),
        ballot("c-b", ranking=("C", "B", "A"), weight=2),
    ], C3


def score_bullet_honest():
    """Cardinal profile: v1 slightly prefers A to B; honest totals elect B."""
    return [
        ballot("v1", scores={"A": 10, "B": 9, "C": 0}),
        ballot("v2", scores={"B": 10, "A": 4, "C": 0}),
        ballot("v3", scores={"C": 10, "B": 3, "A": 0}),
    ], C3


def score_bullet_strategic():
    """v1 bullets A=10, B=0, C=0. A wins; v1 prefers A>B."""
    return [
        ballot("v1", scores={"A": 10, "B": 0, "C": 0}),
        ballot("v2", scores={"B": 10, "A": 4, "C": 0}),
        ballot("v3", scores={"C": 10, "B": 3, "A": 0}),
    ], C3


def approval_bullet_honest():
    return [
        ballot("v1", approved=("A", "B")),
        ballot("v2", approved=("B",)),
        ballot("v3", approved=("A",)),
    ], C3


def approval_bullet_strategic():
    """v1 drops B (bullet). Unique A beats the A/B tie."""
    return [
        ballot("v1", approved=("A",)),
        ballot("v2", approved=("B",)),
        ballot("v3", approved=("A",)),
    ], C3


def two_candidate_honest():
    """May's theorem regime: 3 A>B, 2 B>A. Unique A. Strategy cannot help A-voters."""
    return [
        ballot("a-bloc", ranking=("A", "B"), weight=3,
               scores={"A": 1, "B": 0}, approved=("A",)),
        ballot("b-bloc", ranking=("B", "A"), weight=2,
               scores={"B": 1, "A": 0}, approved=("B",)),
    ], C2


def two_candidate_a_flip():
    """A-bloc ranks B first: makes B win — worse for A-bloc."""
    return [
        ballot("a-bloc", ranking=("B", "A"), weight=3,
               scores={"B": 1, "A": 0}, approved=("B",)),
        ballot("b-bloc", ranking=("B", "A"), weight=2,
               scores={"B": 1, "A": 0}, approved=("B",)),
    ], C2


def unanimous_a():
    return [
        ballot("v1", ranking=("A", "B", "C"),
               scores={"A": 2, "B": 1, "C": 0}, approved=("A",)),
        ballot("v2", ranking=("A", "B", "C"),
               scores={"A": 2, "B": 1, "C": 0}, approved=("A",)),
        ballot("v3", ranking=("A", "B", "C"),
               scores={"A": 2, "B": 1, "C": 0}, approved=("A",)),
    ], C3


def weight_clone_bloc():
    """One weight-5 ballot versus five weight-1 clones. Winners must match."""
    bloc = [ballot("bloc", ranking=("A", "B", "C"), weight=5)]
    clones = [ballot(f"c{i}", ranking=("A", "B", "C"), weight=1) for i in range(5)]
    rest = [
        ballot("opp1", ranking=("B", "C", "A"), weight=2),
        ballot("opp2", ranking=("C", "B", "A"), weight=2),
    ]
    return bloc + rest, clones + rest, C3


irv_compromise_honest = irv_compromise_honest
irv_compromise_strategic = irv_compromise_strategic
irv_five_voter_honest = irv_five_voter_honest
irv_five_voter_strategic = irv_five_voter_strategic
irv_noshow_honest = irv_noshow_honest
irv_noshow_abstain = irv_noshow_abstain
score_bullet_honest = score_bullet_honest
score_bullet_strategic = score_bullet_strategic
approval_bullet_honest = approval_bullet_honest
approval_bullet_strategic = approval_bullet_strategic
two_candidate_honest = two_candidate_honest
two_candidate_a_flip = two_candidate_a_flip
unanimous_a = unanimous_a
weight_clone_bloc = weight_clone_bloc
