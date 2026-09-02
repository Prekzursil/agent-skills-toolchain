#!/usr/bin/env python3
"""Evidence-weighted pairwise Condorcet aggregation (ARC-0070).

Rules are declared here BEFORE any ballot is read:

  * Pairwise votes are evidence-weighted dimension totals, not raw popularity.
  * A citation that fails live path verification is down-weighted to 0.0.
  * A named abstention withdraws that (judge, entry) from pairwise ballots.
  * An unnamed abstention is recorded as a zero (ARC-0069).
  * A Condorcet cycle is REPORTED; the tie-break may still emit a total order
    but must not delete the cycle (cycle_silently_broken is always false).
  * Tie-break order is frozen as TIE_BREAK_ORDER and hashed.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

TIE_BREAK_ORDER = (
    "condorcet_unique",
    "copeland",
    "schulze_strongest_path",
    "evidence_weighted_total",
    "entry_id_lexicographic",
)
FAILED_CITATION_WEIGHT = 0.0
UNNAMED_ABSTENTION_VALUE = 0.0


def tie_break_declaration_sha256() -> str:
    blob = json.dumps(list(TIE_BREAK_ORDER), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def citation_verified(repo: Path, citation: dict) -> bool:
    rel = str(citation.get("path") or "").replace("\\", "/").strip()
    if not rel or rel.startswith("/") or ".." in Path(rel).parts:
        return False
    target = repo / rel
    return target.is_file() and target.stat().st_size > 0


def dimension_weight_map(rubric: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for dim in rubric.get("dimensions") or []:
        if not isinstance(dim, dict):
            continue
        did = str(dim.get("id") or "")
        if not did:
            continue
        try:
            out[did] = float(dim.get("weight") or 0.0)
        except (TypeError, ValueError):
            out[did] = 0.0
    return out


def cell_contribution(
    cell: dict, weight: float, repo: Path
) -> tuple[float | None, str]:
    """Return (contribution, disposition).

    None contribution means the judge is withdrawn from pairwise for this entry
    on this dimension; callers treat a fully-withdrawn entry as withdrawn.
    """
    if not isinstance(cell, dict):
        return UNNAMED_ABSTENTION_VALUE * weight, "unnamed-empty"
    if cell.get("abstention"):
        missing = str(cell.get("missing_evidence") or "").strip()
        if missing:
            return None, "named-abstention"
        return UNNAMED_ABSTENTION_VALUE * weight, "unnamed-abstention-as-zero"
    citations = cell.get("citations") or []
    if not citations:
        return FAILED_CITATION_WEIGHT * weight, "no-citations-downweighted"
    verified = [c for c in citations if isinstance(c, dict) and citation_verified(repo, c)]
    if not verified:
        return FAILED_CITATION_WEIGHT * weight, "failed-citation-downweighted"
    try:
        value = float(cell.get("value"))
    except (TypeError, ValueError):
        return FAILED_CITATION_WEIGHT * weight, "unparseable-value-downweighted"
    return value * weight, "counted"


def judge_entry_total(
    scores: dict, weights: dict[str, float], repo: Path
) -> tuple[float | None, list[dict]]:
    """Weighted total for one (judge, entry). None = fully withdrawn."""
    if not isinstance(scores, dict) or not scores:
        return None, [{"disposition": "empty-scores", "dimension": None}]
    contribs: list[float] = []
    log: list[dict] = []
    any_counted = False
    all_withdrawn = True
    for dim, weight in weights.items():
        cell = scores.get(dim) or {}
        amount, disp = cell_contribution(cell if isinstance(cell, dict) else {}, weight, repo)
        log.append({"dimension": dim, "disposition": disp, "contribution": amount})
        if disp == "named-abstention":
            continue
        all_withdrawn = False
        if amount is None:
            continue
        contribs.append(amount)
        if disp == "counted":
            any_counted = True
    if all_withdrawn:
        return None, log
    if not contribs:
        return None, log
    total = sum(contribs)
    if not any_counted and total == 0.0:
        # Present but fully down-weighted: still a comparable zero, not a withdrawal.
        return 0.0, log
    return total, log


def index_scorecards(doc: dict) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for row in doc.get("scorecards") or []:
        if not isinstance(row, dict):
            continue
        j = str(row.get("judge_id") or "")
        e = str(row.get("entry_id") or "")
        if j and e:
            out[(j, e)] = row
    return out


def entries_and_judges(doc: dict) -> tuple[list[str], list[str]]:
    entries = [str(x) for x in (doc.get("entries") or []) if str(x)]
    judges = [str(x) for x in (doc.get("judges") or []) if str(x)]
    if not entries or not judges:
        seen_e, seen_j = [], []
        for row in doc.get("scorecards") or []:
            if not isinstance(row, dict):
                continue
            e, j = str(row.get("entry_id") or ""), str(row.get("judge_id") or "")
            if e and e not in seen_e:
                seen_e.append(e)
            if j and j not in seen_j:
                seen_j.append(j)
        entries = entries or seen_e
        judges = judges or seen_j
    return sorted(entries), sorted(judges)


def totals_table(
    scorecards: dict, rubric: dict, repo: Path
) -> tuple[dict[tuple[str, str], float | None], list[dict]]:
    weights = dimension_weight_map(rubric)
    entries, judges = entries_and_judges(scorecards)
    indexed = index_scorecards(scorecards)
    table: dict[tuple[str, str], float | None] = {}
    log: list[dict] = []
    for j in judges:
        for e in entries:
            row = indexed.get((j, e), {})
            total, cell_log = judge_entry_total(row.get("scores") or {}, weights, repo)
            table[(j, e)] = total
            log.append({"judge_id": j, "entry_id": e, "total": total, "cells": cell_log})
    return table, log


def pairwise_from_totals(
    entries: list[str], judges: list[str], table: dict[tuple[str, str], float | None]
) -> list[dict]:
    pairs: list[dict] = []
    for i, a in enumerate(entries):
        for b in entries[i + 1 :]:
            a_votes = b_votes = ties = 0
            for j in judges:
                sa, sb = table.get((j, a)), table.get((j, b))
                if sa is None or sb is None:
                    continue
                if sa > sb:
                    a_votes += 1
                elif sb > sa:
                    b_votes += 1
                else:
                    ties += 1
            decided = a_votes + b_votes
            undecided = decided == 0
            winner = None
            if a_votes > b_votes:
                winner = a
            elif b_votes > a_votes:
                winner = b
            pairs.append(
                {
                    "a": a,
                    "b": b,
                    "a_votes": a_votes,
                    "b_votes": b_votes,
                    "ties": ties,
                    "undecided": undecided,
                    "margin": a_votes - b_votes,
                    "winner": winner,
                }
            )
    return pairs


def majority_edges(pairs: list[dict]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for p in pairs:
        w = p.get("winner")
        if not w:
            continue
        loser = p["b"] if w == p["a"] else p["a"]
        graph[str(w)].add(str(loser))
    return graph


def find_cycles(entries: list[str], graph: dict[str, set[str]]) -> list[list[str]]:
    """Simple cycles, canonicalized (rotate to lexicographically smallest, then direction)."""
    found: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()

    def canon(path: list[str]) -> tuple[str, ...]:
        n = len(path)
        rot = min(range(n), key=lambda i: path[i])
        fwd = path[rot:] + path[:rot]
        rev = list(reversed(path))
        rot_r = min(range(n), key=lambda i: rev[i])
        bwd = rev[rot_r:] + rev[:rot_r]
        pick = fwd if tuple(fwd) <= tuple(bwd) else bwd
        return tuple(pick)

    def dfs(start: str, node: str, path: list[str], stack: set[str]) -> None:
        for nxt in sorted(graph.get(node, ())):
            if nxt == start and len(path) >= 3:
                c = canon(path)
                if c not in seen:
                    seen.add(c)
                    found.append(list(c))
            elif nxt not in stack and nxt >= start:
                stack.add(nxt)
                path.append(nxt)
                dfs(start, nxt, path, stack)
                path.pop()
                stack.remove(nxt)

    for start in entries:
        dfs(start, start, [start], {start})
    found.sort(key=lambda c: (len(c), c))
    return found


def condorcet_winner(entries: list[str], graph: dict[str, set[str]]) -> str | None:
    winners = []
    for e in entries:
        beaten = graph.get(e, set())
        others = set(entries) - {e}
        if others and others <= beaten:
            winners.append(e)
    if len(winners) == 1:
        return winners[0]
    return None


def copeland_scores(entries: list[str], pairs: list[dict]) -> dict[str, int]:
    scores = {e: 0 for e in entries}
    for p in pairs:
        w = p.get("winner")
        if not w:
            continue
        loser = p["b"] if w == p["a"] else p["a"]
        scores[str(w)] += 1
        scores[str(loser)] -= 1
    return scores


def schulze_strength(entries: list[str], pairs: list[dict]) -> dict[tuple[str, str], int]:
    idx = {e: i for i, e in enumerate(entries)}
    n = len(entries)
    d = [[0] * n for _ in range(n)]
    for p in pairs:
        a, b = str(p["a"]), str(p["b"])
        if a not in idx or b not in idx:
            continue
        i, j = idx[a], idx[b]
        if p.get("winner") == a:
            d[i][j] = int(p["a_votes"])
        elif p.get("winner") == b:
            d[j][i] = int(p["b_votes"])
    pth = [row[:] for row in d]
    for k in range(n):
        for i in range(n):
            if i == k:
                continue
            for j in range(n):
                if j == i or j == k:
                    continue
                pth[i][j] = max(pth[i][j], min(pth[i][k], pth[k][j]))
    out: dict[tuple[str, str], int] = {}
    for i, a in enumerate(entries):
        for j, b in enumerate(entries):
            if i == j:
                continue
            out[(a, b)] = pth[i][j]
    return out


def evidence_totals(
    entries: list[str], judges: list[str], table: dict[tuple[str, str], float | None]
) -> dict[str, float]:
    sums = {e: 0.0 for e in entries}
    for e in entries:
        for j in judges:
            v = table.get((j, e))
            if v is not None:
                sums[e] += float(v)
    return sums


def sort_entries(
    entries: list[str],
    pairs: list[dict],
    table: dict[tuple[str, str], float | None],
    judges: list[str],
) -> tuple[list[str], bool]:
    """Total order via declared tie-break. Returns (order, tie_break_applied)."""
    graph = majority_edges(pairs)
    unique = condorcet_winner(entries, graph)
    cop = copeland_scores(entries, pairs)
    schulze = schulze_strength(entries, pairs)
    ev = evidence_totals(entries, judges, table)

    def schulze_key(e: str) -> tuple:
        wins = sum(1 for o in entries if o != e and schulze[(e, o)] > schulze[(o, e)])
        strength = sum(schulze[(e, o)] - schulze[(o, e)] for o in entries if o != e)
        return (wins, strength)

    def key(e: str) -> tuple:
        return (
            0 if e == unique else 1,
            -cop[e],
            -schulze_key(e)[0],
            -schulze_key(e)[1],
            -ev[e],
            e,
        )

    ordered = sorted(entries, key=key)
    applied = unique is None
    return ordered, applied


def ranking_rows(
    order: list[str],
    pairs: list[dict],
    table: dict[tuple[str, str], float | None],
    judges: list[str],
) -> list[dict]:
    cop = copeland_scores(order, pairs)
    ev = evidence_totals(order, judges, table)
    schulze = schulze_strength(order, pairs)
    rows = []
    for i, e in enumerate(order, 1):
        sch_wins = sum(1 for o in order if o != e and schulze[(e, o)] > schulze[(o, e)])
        rows.append(
            {
                "rank": i,
                "entry_id": e,
                "copeland": cop[e],
                "schulze_wins": sch_wins,
                "evidence_weighted_total": round(ev[e], 6),
            }
        )
    return rows


def aggregate(scorecards: dict, rubric: dict, repo: Path) -> dict:
    entries, judges = entries_and_judges(scorecards)
    if len(entries) < 2:
        raise ValueError("need at least two entries")
    table, log = totals_table(scorecards, rubric, repo)
    pairs = pairwise_from_totals(entries, judges, table)
    graph = majority_edges(pairs)
    cycles = find_cycles(entries, graph)
    winner = condorcet_winner(entries, graph)
    order, tb_applied = sort_entries(entries, pairs, table, judges)
    downweighted = [
        row
        for row in log
        if any(
            str(c.get("disposition") or "").endswith("downweighted") for c in row.get("cells") or []
        )
    ]
    return {
        "entries": entries,
        "judges": judges,
        "pairwise_matrix": pairs,
        "cycles": [{"members": c, "reported": True} for c in cycles],
        "condorcet_winner": winner,
        "ranking": ranking_rows(order, pairs, table, judges),
        "tie_break_applied": tb_applied,
        "cycle_silently_broken": False,
        "downweighted_cells": downweighted,
        "totals_log": log,
        "evidence_weighted_totals": {k: round(v, 6) for k, v in evidence_totals(entries, judges, table).items()},
        "copeland": copeland_scores(entries, pairs),
    }


def drop_judge(scorecards: dict, judge_id: str) -> dict:
    clone = json.loads(json.dumps(scorecards))
    clone["judges"] = [j for j in (clone.get("judges") or []) if j != judge_id]
    clone["scorecards"] = [
        r
        for r in (clone.get("scorecards") or [])
        if not (isinstance(r, dict) and r.get("judge_id") == judge_id)
    ]
    return clone


def kendall_disagreements(order_a: list[str], order_b: list[str]) -> int:
    pos_a = {e: i for i, e in enumerate(order_a)}
    pos_b = {e: i for i, e in enumerate(order_b)}
    keys = [e for e in order_a if e in pos_b]
    n = 0
    for i, x in enumerate(keys):
        for y in keys[i + 1 :]:
            if (pos_a[x] < pos_a[y]) != (pos_b[x] < pos_b[y]):
                n += 1
    return n


def sensitivity(scorecards: dict, rubric: dict, repo: Path) -> dict:
    base = aggregate(scorecards, rubric, repo)
    base_order = [r["entry_id"] for r in base["ranking"]]
    base_winner = base_order[0] if base_order else None
    judges = list(base["judges"])
    rows = []
    best = None
    for j in judges:
        dropped = aggregate(drop_judge(scorecards, j), rubric, repo)
        order = [r["entry_id"] for r in dropped["ranking"]]
        dwin = order[0] if order else None
        rec = {
            "dropped_judge": j,
            "winner": dwin,
            "winner_changed": dwin != base_winner,
            "kendall_disagreements": kendall_disagreements(base_order, order),
            "ranking": order,
        }
        rows.append(rec)
        if best is None:
            best = rec
            continue
        key = (rec["kendall_disagreements"], rec["winner_changed"], rec["dropped_judge"])
        bkey = (best["kendall_disagreements"], best["winner_changed"], best["dropped_judge"])
        if key > bkey:
            best = rec
    return {
        "baseline_winner": base_winner,
        "most_influential_judge": None if best is None else best["dropped_judge"],
        "winner_changed": False if best is None else bool(best["winner_changed"]),
        "dropped_winner": None if best is None else best["winner"],
        "per_judge": rows,
    }
