"""Paired workflow tournament with an injected exact-tie (IMP-0200)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

CORPUS_ID = "imp-0200-matched-corpus"


@dataclass
class PairOutcome:
    outcome: str
    wins_a: int
    wins_b: int


@dataclass
class RankRow:
    rank: int
    workflow_id: str


@dataclass
class Tournament:
    candidates: list[str]
    ranking: list[RankRow]
    pairs: list[dict[str, Any]]
    forced_total_order: bool = False

    def matrix_archive(self) -> dict[str, Any]:
        return {
            "pairs": list(self.pairs),
            "forced_total_order": self.forced_total_order,
            "candidates": list(self.candidates),
            "corpus_id": CORPUS_ID,
        }


def matched_corpus() -> list[dict[str, Any]]:
    # 8 cases. Twin-left and twin-right score identically on every case.
    cases = []
    for i in range(8):
        cases.append({"id": f"case-{i}", "label": "even" if i % 2 == 0 else "odd"})
    return cases


def scorers() -> dict[str, dict[str, int]]:
    cases = matched_corpus()
    champion = {c["id"]: (2 if c["label"] == "even" else 1) for c in cases}
    weak = {c["id"]: 0 for c in cases}
    twin = {c["id"]: 1 for c in cases}
    return {
        "champion": champion,
        "weak": weak,
        "twin-left": dict(twin),
        "twin-right": dict(twin),
        "mid": {c["id"]: (1 if c["label"] == "even" else 0) for c in cases},
    }


def injected_tie_ids() -> tuple[str, str]:
    return ("twin-left", "twin-right")


def clear_winner_ids() -> tuple[str, str]:
    return ("champion", "weak")


def eval_cases(corpus: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    return list(corpus or matched_corpus())


def compare_pair(
    a: str,
    b: str,
    scores_a: dict[str, int],
    scores_b: dict[str, int],
    cases: Iterable[dict[str, Any]],
) -> PairOutcome:
    wins_a = wins_b = 0
    for case in cases:
        cid = case["id"]
        sa = int(scores_a.get(cid, 0))
        sb = int(scores_b.get(cid, 0))
        if sa > sb:
            wins_a += 1
        elif sb > sa:
            wins_b += 1
    if wins_a == wins_b:
        outcome = "TIE"
    elif wins_a > wins_b:
        outcome = "A_WINS"
    else:
        outcome = "B_WINS"
    return PairOutcome(outcome=outcome, wins_a=wins_a, wins_b=wins_b)


def run_round_robin(
    score_map: dict[str, dict[str, int]],
    corpus: list[dict[str, Any]],
    corpus_id: str = CORPUS_ID,
) -> Tournament:
    ids = list(score_map)
    pairs = []
    wins: dict[str, int] = {i: 0 for i in ids}
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            out = compare_pair(a, b, score_map[a], score_map[b], corpus)
            pairs.append(
                {
                    "a": a,
                    "b": b,
                    "outcome": out.outcome,
                    "wins_a": out.wins_a,
                    "wins_b": out.wins_b,
                }
            )
            if out.outcome == "A_WINS":
                wins[a] += 1
            elif out.outcome == "B_WINS":
                wins[b] += 1
    # Rank by wins desc; ties share rank.
    ordered = sorted(ids, key=lambda i: (-wins[i], i))
    ranking: list[RankRow] = []
    last_wins = None
    rank = 0
    for i, wid in enumerate(ordered, 1):
        if last_wins is None or wins[wid] != last_wins:
            rank = i
            last_wins = wins[wid]
        ranking.append(RankRow(rank=rank, workflow_id=wid))
    return Tournament(candidates=ids, ranking=ranking, pairs=pairs)


def rank_from_matrix_archive(archive: dict[str, Any]) -> tuple[list[RankRow], list[list[str]], bool]:
    ids = list(archive.get("candidates") or [])
    wins = {i: 0 for i in ids}
    for pair in archive.get("pairs") or []:
        if pair["outcome"] == "A_WINS":
            wins[pair["a"]] += 1
        elif pair["outcome"] == "B_WINS":
            wins[pair["b"]] += 1
    ordered = sorted(ids, key=lambda i: (-wins[i], i))
    ranking: list[RankRow] = []
    last = None
    rank = 0
    groups: dict[int, list[str]] = {}
    for i, wid in enumerate(ordered, 1):
        if last is None or wins[wid] != last:
            rank = i
            last = wins[wid]
        ranking.append(RankRow(rank=rank, workflow_id=wid))
        groups.setdefault(rank, []).append(wid)
    group_list = [groups[k] for k in sorted(groups)]
    forced = bool(archive.get("forced_total_order"))
    return ranking, group_list, forced


def fabricated_total_order(archive: dict[str, Any]) -> list[dict[str, Any]]:
    ids = sorted(archive.get("candidates") or [])
    return [{"workflow_id": wid, "rank": i} for i, wid in enumerate(ids, 1)]


def rank_map(ranking: list[RankRow]) -> dict[str, int]:
    return {r.workflow_id: int(r.rank) for r in ranking}
