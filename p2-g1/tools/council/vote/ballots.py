"""Ballot methods with textbook fixtures (IMP-0303).

RANKED_CHOICE is IRV. SCORE on ranked ballots is Borda (3-2-1-0).
APPROVAL on ranked ballots is top-2. Binding a method as default is banned.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

APPROVAL = "approval"
PAIRWISE = "pairwise-condorcet"
RANKED_CHOICE = "ranked-choice"
SCORE = "score"
METHODS = (RANKED_CHOICE, PAIRWISE, SCORE, APPROVAL)


@dataclass
class Ballot:
    ranking: tuple[str, ...] = ()
    scores: dict[str, int] | None = None
    approvals: tuple[str, ...] | None = None
    weight: int = 1
    kind: str = "ordinal"
    voter_id: str = ""

    @classmethod
    def from_parts(
        cls,
        voter_id: str,
        *,
        ranking: Sequence[str] = (),
        scores: dict[str, int] | None = None,
        approved: Iterable[str] = (),
        weight: int = 1,
    ) -> "Ballot":
        approved_t = tuple(approved)
        kind = "cardinal" if scores else ("approval" if approved_t else "ordinal")
        return cls(
            ranking=tuple(ranking),
            scores=scores,
            approvals=approved_t or None,
            weight=int(weight),
            kind=kind,
            voter_id=str(voter_id),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "voter_id": self.voter_id,
            "ranking": list(self.ranking),
            "scores": dict(self.scores) if self.scores else None,
            "approvals": list(self.approvals) if self.approvals is not None else None,
            "weight": self.weight,
            "kind": self.kind,
        }


@dataclass
class MethodResult:
    method: str
    winner: str | None
    status: str
    totals: dict[str, int] = field(default_factory=dict)
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "winner": self.winner,
            "status": self.status,
            "totals": self.totals,
            "detail": self.detail,
        }


@dataclass
class Report:
    by_method: dict[str, MethodResult]
    winners_by_method: dict[str, str | None]
    divergent: bool
    binding_winner: str | None
    owner_action: str
    agreed_winner: str | None
    cycle_reported: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "winners_by_method": self.winners_by_method,
            "divergent": self.divergent,
            "binding_winner": self.binding_winner,
            "owner_action": self.owner_action,
            "agreed_winner": self.agreed_winner,
            "cycle_reported": self.cycle_reported,
            "methods": {k: v.to_dict() for k, v in self.by_method.items()},
        }


@dataclass
class Fixture:
    ballots: list[Ballot]
    candidates: list[str]


def _weighted(ballots: list[Ballot]) -> list[Ballot]:
    out: list[Ballot] = []
    for b in ballots:
        out.extend([b] * max(1, int(b.weight)))
    return out


def _irv(ballots: list[Ballot], candidates: list[str]) -> MethodResult:
    ordinal = [b for b in ballots if b.ranking]
    if not ordinal:
        return MethodResult(RANKED_CHOICE, None, "NO_ORDINAL_BALLOTS")
    remaining = list(candidates)
    rounds: list[dict[str, Any]] = []
    winner = None
    while remaining:
        counts = {c: 0 for c in remaining}
        for b in ordinal:
            for c in b.ranking:
                if c in remaining:
                    counts[c] += b.weight
                    break
        rounds.append({"counts": dict(counts)})
        total = sum(counts.values())
        for c, n in counts.items():
            if total and n * 2 > total:
                winner = c
                remaining = [c]
                break
        else:
            loser = min(remaining, key=lambda c: (counts[c], remaining.index(c)))
            remaining = [c for c in remaining if c != loser]
            if len(remaining) == 1:
                winner = remaining[0]
                break
            continue
        break
    return MethodResult(
        RANKED_CHOICE,
        winner,
        "IRV_WINNER" if winner else "IRV_INCONCLUSIVE",
        totals=rounds[-1]["counts"] if rounds else {},
        detail={"rounds": rounds},
    )


def _pairwise(ballots: list[Ballot], candidates: list[str]) -> MethodResult:
    ordinal = [b for b in ballots if b.ranking]
    if not ordinal:
        return MethodResult(PAIRWISE, None, "NO_ORDINAL_BALLOTS")
    matrix: dict[str, dict[str, Any]] = {}
    pref = {a: {b: 0 for b in candidates if b != a} for a in candidates}
    for b in ordinal:
        rank = {c: i for i, c in enumerate(b.ranking)}
        for a in candidates:
            for c in candidates:
                if a == c or a not in rank or c not in rank:
                    continue
                if rank[a] < rank[c]:
                    pref[a][c] += b.weight
    for a in candidates:
        for c in candidates:
            if a == c:
                continue
            matrix[f"{a}>{c}"] = {
                "for": pref[a][c],
                "against": pref[c][a],
                "beats": pref[a][c] > pref[c][a],
            }
    condorcet = None
    for a in candidates:
        if all(pref[a][c] > pref[c][a] for c in candidates if c != a):
            condorcet = a
            break
    cycle = condorcet is None
    return MethodResult(
        PAIRWISE,
        condorcet,
        "CONDORCET_WINNER" if condorcet else "CONDORCET_CYCLE",
        detail={"pairwise_matrix": matrix, "cycle": cycle},
    )


def _borda(ballots: list[Ballot], candidates: list[str]) -> MethodResult:
    n = len(candidates)
    totals = {c: 0 for c in candidates}
    scored = False
    for b in ballots:
        if b.scores:
            scored = True
            for c, s in b.scores.items():
                if c in totals:
                    totals[c] += int(s) * b.weight
            continue
        if b.ranking:
            scored = True
            for i, c in enumerate(b.ranking):
                if c in totals:
                    totals[c] += (n - 1 - i) * b.weight
    if not scored:
        return MethodResult(SCORE, None, "NO_SCORE_BALLOTS")
    winner = max(totals, key=lambda c: (totals[c], -candidates.index(c)))
    return MethodResult(SCORE, winner, "BORDA_OR_SCORE", totals=totals)


def _approval(ballots: list[Ballot], candidates: list[str]) -> MethodResult:
    totals = {c: 0 for c in candidates}
    any_app = False
    for b in ballots:
        if b.approvals is not None:
            any_app = True
            for c in b.approvals:
                if c in totals:
                    totals[c] += b.weight
            continue
        if b.ranking:
            any_app = True
            for c in b.ranking[:2]:
                if c in totals:
                    totals[c] += b.weight
    if not any_app:
        return MethodResult(APPROVAL, None, "NO_APPROVAL_BALLOTS")
    top = max(totals.values()) if totals else 0
    tied = [c for c in candidates if totals.get(c, 0) == top]
    if len(tied) != 1:
        return MethodResult(APPROVAL, None, "APPROVAL_TIE", totals=totals)
    return MethodResult(APPROVAL, tied[0], "APPROVAL_WINNER", totals=totals)


def evaluate_all(ballots: list[Ballot], candidates: list[str]) -> Report:
    methods = {
        RANKED_CHOICE: _irv(ballots, candidates),
        PAIRWISE: _pairwise(ballots, candidates),
        SCORE: _borda(ballots, candidates),
        APPROVAL: _approval(ballots, candidates),
    }
    winners = {k: v.winner for k, v in methods.items()}
    named = {w for w in winners.values() if w}
    divergent = len(named) > 1
    cycle = methods[PAIRWISE].status == "CONDORCET_CYCLE"
    return Report(
        by_method=methods,
        winners_by_method=winners,
        divergent=divergent or cycle,
        binding_winner=None,
        owner_action="SURFACE_DIVERGENCE" if divergent or cycle else "RECORD_AGREEMENT",
        agreed_winner=None if divergent or cycle else next(iter(named), None),
        cycle_reported=cycle,
    )


def hides_divergence(report: Report) -> bool:
    return report.binding_winner is not None and report.divergent


def mutant_silent_default(report: Report, method: str) -> Report:
    winner = report.winners_by_method.get(method)
    return Report(
        by_method=report.by_method,
        winners_by_method=report.winners_by_method,
        divergent=report.divergent,
        binding_winner=winner,
        owner_action="BIND_DEFAULT",
        agreed_winner=winner,
        cycle_reported=report.cycle_reported,
    )


def _copies(ranking: tuple[str, ...], n: int) -> list[Ballot]:
    return [Ballot(ranking=ranking, weight=1) for _ in range(n)]


def textbook_fixtures() -> dict[str, Fixture]:
    tn_cands = ["Memphis", "Nashville", "Chattanooga", "Knoxville"]
    tn = (
        _copies(("Memphis", "Nashville", "Chattanooga", "Knoxville"), 42)
        + _copies(("Nashville", "Chattanooga", "Knoxville", "Memphis"), 26)
        + _copies(("Chattanooga", "Knoxville", "Nashville", "Memphis"), 15)
        + _copies(("Knoxville", "Chattanooga", "Nashville", "Memphis"), 17)
    )
    irv3 = (
        _copies(("A", "B", "C"), 4)
        + _copies(("B", "C", "A"), 3)
        + _copies(("C", "B", "A"), 2)
    )
    score = [
        Ballot(scores={"A": 7, "B": 9, "C": 3}, kind="cardinal"),
        Ballot(scores={"A": 7, "B": 10, "C": 6}, kind="cardinal"),
    ]
    approval = [
        Ballot(approvals=("Andrea", "Brad"), kind="approval"),
        Ballot(approvals=("Andrea", "Brad"), kind="approval"),
        Ballot(approvals=("Andrea", "Carter"), kind="approval"),
    ]
    cycle = (
        _copies(("A", "B", "C"), 4)
        + _copies(("B", "C", "A"), 3)
        + _copies(("C", "A", "B"), 2)
    )
    return {
        "tennessee-capital": Fixture(tn, tn_cands),
        "irv-three-candidate": Fixture(irv3, ["A", "B", "C"]),
        "score-range-0-9": Fixture(score, ["A", "B", "C"]),
        "approval-andrea": Fixture(approval, ["Andrea", "Brad", "Carter"]),
        "condorcet-cycle-unequal": Fixture(cycle, ["A", "B", "C"]),
    }


def fixture_reports() -> dict[str, dict[str, Any]]:
    out = {}
    for name, fx in textbook_fixtures().items():
        out[name] = evaluate_all(fx.ballots, fx.candidates).to_dict()
    return out


ranked_choice = _irv
pairwise_condorcet = _pairwise
score = _borda
approval = _approval
