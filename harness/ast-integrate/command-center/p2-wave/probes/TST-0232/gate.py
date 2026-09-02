"""Visible/holdout gap gate.

Always reports both scores. Refuses a verdict on an undersized split.
Fails a candidate when visible_score - holdout_score exceeds the declared
threshold. The threshold is versioned and is not retuned per run.
"""
from __future__ import annotations

import contract as C
from corpus import PredictFn, honest_predict, overfit_predict_factory


def score_split(predict: PredictFn, cases: list) -> dict:
    n = len(cases)
    if n == 0:
        raise ValueError("empty split: gate refuses to score nothing")
    hits = 0
    rows = []
    for case in cases:
        pred = predict(case["id"], list(case["payload"]))
        ok = pred == case["expected"]
        hits += int(ok)
        rows.append(
            {
                "id": case["id"],
                "expected": case["expected"],
                "predicted": pred,
                "ok": ok,
            }
        )
    return {"n": n, "hits": hits, "score": hits / n, "rows": rows}


def evaluate(
    predict: PredictFn,
    visible: list,
    holdout: list,
    *,
    candidate_id: str,
    threshold: float = C.GAP_THRESHOLD,
    min_split: int = C.MIN_SPLIT,
) -> dict:
    n_v, n_h = len(visible), len(holdout)
    if n_v < min_split or n_h < min_split:
        return {
            "id": candidate_id,
            "visible_score": None,
            "holdout_score": None,
            "n_visible": n_v,
            "n_holdout": n_h,
            "gap": None,
            "threshold": threshold,
            "threshold_version": C.THRESHOLD_VERSION,
            "formula": C.THRESHOLD_FORMULA,
            "verdict": "INSUFFICIENT",
            "gaming": False,
            "both_scores_reported": False,
            "reason": (
                f"refusing verdict: n_visible={n_v} n_holdout={n_h} "
                f"min_split={min_split}"
            ),
        }
    vis = score_split(predict, visible)
    hol = score_split(predict, holdout)
    gap = vis["score"] - hol["score"]
    gaming = gap > threshold
    return {
        "id": candidate_id,
        "visible_score": vis["score"],
        "holdout_score": hol["score"],
        "n_visible": vis["n"],
        "n_holdout": hol["n"],
        "visible_hits": vis["hits"],
        "holdout_hits": hol["hits"],
        "gap": gap,
        "threshold": threshold,
        "threshold_version": C.THRESHOLD_VERSION,
        "formula": C.THRESHOLD_FORMULA,
        "verdict": "FAIL_GAMING" if gaming else "PASS",
        "gaming": gaming,
        "visible_rows": vis["rows"],
        "holdout_rows": hol["rows"],
        "both_scores_reported": True,
    }


def compact(result: dict) -> dict:
    keys = (
        "id",
        "visible_score",
        "holdout_score",
        "n_visible",
        "n_holdout",
        "visible_hits",
        "holdout_hits",
        "gap",
        "threshold",
        "threshold_version",
        "formula",
        "verdict",
        "gaming",
        "both_scores_reported",
    )
    return {k: result[k] for k in keys if k in result}


def both_states(visible: list, holdout: list) -> dict:
    honest = evaluate(honest_predict, visible, holdout, candidate_id="honest")
    overfit = evaluate(
        overfit_predict_factory(visible),
        visible,
        holdout,
        candidate_id="fixture-overfit",
    )
    return {
        "honest": honest,
        "overfit": overfit,
        "overfit_fired": overfit["verdict"] == "FAIL_GAMING",
        "honest_silent": honest["verdict"] == "PASS",
        "threshold": C.GAP_THRESHOLD,
        "threshold_version": C.THRESHOLD_VERSION,
    }
