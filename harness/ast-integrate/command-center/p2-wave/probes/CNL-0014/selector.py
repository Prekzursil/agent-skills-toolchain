"""Calibration-ranked selector. Zero-history is UNRANKABLE, never average."""
from __future__ import annotations

from typing import Any

import store as S


def _lookup_n(store: dict, participant_id: str, task_class: str) -> int:
    return S.resolved_n(store, participant_id, task_class)


def rank_calibration(
    store: dict,
    candidates: list[dict],
    k: int | None = None,
) -> dict[str, Any]:
    """Honest selector: rank only RANK_ELIGIBLE rows by ascending Brier.

    Does not switch method when the ranked list is empty. Zero-history
    candidates are returned only under unrankable with reason ZERO_HISTORY.
    """
    ranked: list[dict] = []
    unrankable: list[dict] = []
    for cand in candidates:
        pid = cand["participant_id"]
        task = cand["task_class"]
        S.observe_candidate(store, pid, task)
        rec = S.find_record(store, pid, task)
        assert rec is not None
        n = _lookup_n(store, pid, task)
        if rec["rank_class"] != "RANK_ELIGIBLE" or rec["brier"] is None or n < store["min_resolved_n"]:
            unrankable.append(
                {
                    "participant_id": pid,
                    "task_class": task,
                    "reason": "ZERO_HISTORY" if n == 0 else "BELOW_MIN_RESOLVED_N",
                    "resolved_n": n,
                    "brier": None,
                }
            )
            continue
        ranked.append(
            {
                "participant_id": pid,
                "task_class": task,
                "resolved_n": n,
                "brier": float(rec["brier"]),
            }
        )
    ranked.sort(key=lambda row: (row["brier"], row["participant_id"]))
    for i, row in enumerate(ranked, 1):
        row["rank"] = i
    if k is not None:
        overflow = ranked[k:]
        ranked = ranked[:k]
        for row in overflow:
            unrankable.append(
                {
                    "participant_id": row["participant_id"],
                    "task_class": row["task_class"],
                    "reason": "OUTSIDE_TOP_K",
                    "resolved_n": row["resolved_n"],
                    "brier": row["brier"],
                }
            )
    return {
        "method": "calibration-rank",
        "switched_method": False,
        "ranked": ranked,
        "unrankable": unrankable,
    }


def rank_with_average_imputation(
    store: dict,
    candidates: list[dict],
    k: int | None = None,
) -> dict[str, Any]:
    """Rejected behaviour: treat missing history as the pool average (or 0.5).

    This is the planted-bad selector. Zero-history participants receive a
    numeric Brier and appear on the ranked roster.
    """
    eligible_scores: list[float] = []
    for cand in candidates:
        rec = S.find_record(store, cand["participant_id"], cand["task_class"])
        if rec is not None and rec["brier"] is not None and rec["rank_class"] == "RANK_ELIGIBLE":
            eligible_scores.append(float(rec["brier"]))
    if eligible_scores:
        imputed = sum(eligible_scores) / len(eligible_scores)
        impute_source = "pool-mean"
    else:
        imputed = 0.5
        impute_source = "uninformative-0.5"
    ranked: list[dict] = []
    for cand in candidates:
        pid = cand["participant_id"]
        task = cand["task_class"]
        n = _lookup_n(store, pid, task)
        rec = S.find_record(store, pid, task)
        if rec is not None and rec["brier"] is not None and rec["rank_class"] == "RANK_ELIGIBLE":
            brier = float(rec["brier"])
            invented = False
        else:
            brier = imputed
            invented = True
        ranked.append(
            {
                "participant_id": pid,
                "task_class": task,
                "resolved_n": n,
                "brier": brier,
                "imputed": invented,
                "impute_source": impute_source if invented else None,
            }
        )
    ranked.sort(key=lambda row: (row["brier"], row["participant_id"]))
    for i, row in enumerate(ranked, 1):
        row["rank"] = i
    if k is not None:
        ranked = ranked[:k]
    return {
        "method": "calibration-rank",
        "switched_method": False,
        "ranked": ranked,
        "unrankable": [],
        "imputed_average": imputed,
        "impute_source": impute_source,
    }


def disjoint_zero_history(store: dict, ranking: dict, candidates: list[dict]) -> dict[str, Any]:
    """Independent signal: set algebra over raw SCOREABLE counts vs ranked ids."""
    zero: set[str] = set()
    ranked_ids = {row["participant_id"] for row in ranking.get("ranked") or []}
    for cand in candidates:
        pid = cand["participant_id"]
        task = cand["task_class"]
        n = S.resolved_n(store, pid, task)
        if n < store["min_resolved_n"]:
            zero.add(pid)
    overlap = sorted(zero & ranked_ids)
    return {
        "zero_history_ids": sorted(zero),
        "ranked_ids": sorted(ranked_ids),
        "overlap": overlap,
        "disjoint": len(overlap) == 0,
    }
