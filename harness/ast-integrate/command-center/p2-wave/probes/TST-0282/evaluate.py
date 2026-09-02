"""Score the gold set and compute held-out correlation."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import gold as G  # noqa: E402
import stats as ST  # noqa: E402
from council.completeness import (  # noqa: E402
    FORMULA_ID,
    THRESHOLD,
    score_output,
)

MIN_HELDOUT_N = 10
MIN_SPEARMAN = 0.70
MIN_BOOTSTRAP_LO = 0.40


def per_case_rows(cases: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = []
    for case in cases or G.all_cases():
        scored = score_output(case["objective"], case["output"])
        rows.append(
            {
                "id": case["id"],
                "split": case["split"],
                "kind": case["kind"],
                "human_label": case["human_label"],
                "rubric": case["rubric"],
                "score": scored["score"],
                "unverified": scored["unverified"],
                "gate_fires": scored["gate_fires"],
                "components": scored["components"],
                "word_count": scored["word_count"],
                "ignored_undeclared_answers": scored["ignored_undeclared_answers"],
            }
        )
    return rows


def heldout_rows(rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    data = rows if rows is not None else per_case_rows()
    return [r for r in data if r["split"] == "heldout" and r["score"] is not None]


def correlation_report(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    held = heldout_rows(rows)
    xs = [float(r["score"]) for r in held]
    ys = [float(r["human_label"]) for r in held]
    ws = [float(r["word_count"]) for r in held]
    rho = ST.spearman(xs, ys)
    boot_lo, boot_hi = ST.bootstrap_spearman_ci(xs, ys)
    fish_lo, fish_hi = ST.fisher_z_ci(rho, len(held))
    rho_len = ST.spearman(ws, ys)
    n_distinct_scores = len({round(x, 6) for x in xs})
    n_distinct_labels = len({round(y, 6) for y in ys})
    validated = (
        len(held) >= MIN_HELDOUT_N
        and n_distinct_scores >= 3
        and n_distinct_labels >= 3
        and rho == rho
        and rho >= MIN_SPEARMAN
        and boot_lo == boot_lo
        and boot_lo > MIN_BOOTSTRAP_LO
    )
    return {
        "formula_id": FORMULA_ID,
        "n_heldout": len(held),
        "spearman_rho": rho,
        "bootstrap_ci95": [boot_lo, boot_hi],
        "fisher_z_ci95": [fish_lo, fish_hi],
        "word_count_spearman_rho": rho_len,
        "n_distinct_scores": n_distinct_scores,
        "n_distinct_labels": n_distinct_labels,
        "min_spearman_a_priori": MIN_SPEARMAN,
        "min_bootstrap_lo_a_priori": MIN_BOOTSTRAP_LO,
        "validated": validated,
        "pairs": [
            {
                "id": r["id"],
                "score": r["score"],
                "human_label": r["human_label"],
                "word_count": r["word_count"],
            }
            for r in held
        ],
    }


def both_states(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    data = rows if rows is not None else per_case_rows()
    by_id = {r["id"]: r for r in data}
    complete = by_id[G.COMPLETE_ID]
    padded = by_id[G.PADDED_ID]
    extra = by_id["heldout.complete-padded-extra"]
    cscore = complete["score"]
    pscore = padded["score"]
    escore = extra["score"]
    return {
        "complete_id": G.COMPLETE_ID,
        "complete_score": cscore,
        "complete_reaches_threshold": cscore is not None and cscore >= THRESHOLD,
        "padded_id": G.PADDED_ID,
        "padded_score": pscore,
        "padded_below_threshold": pscore is not None and pscore < THRESHOLD,
        "padded_word_count": padded["word_count"],
        "complete_word_count": complete["word_count"],
        "padding_is_heavier": padded["word_count"] > complete["word_count"],
        "extra_padding_still_complete": escore is not None and escore >= THRESHOLD,
        "threshold": THRESHOLD,
    }


def empty_objective_control() -> dict[str, Any]:
    scored = score_output({"subquestions": [], "required_categories": [], "evidence_classes": []}, {"answers": []})
    return {
        "unverified": scored["unverified"],
        "score": scored["score"],
        "gate_fires": scored["gate_fires"],
        "may_bind_stopping_rule": scored["may_bind_stopping_rule"],
    }


def scorer_ignores_labels() -> bool:
    obj = G.default_objective()
    out = G.make_output(
        sq_ids=["sq-def", "sq-val"],
        categories=["findings"],
        evidence_classes=["measurement"],
    )
    a = score_output(obj, out)
    poisoned_obj = dict(obj)
    poisoned_obj["human_label"] = 0.0
    poisoned_obj["rubric"] = 0
    poisoned_out = dict(out)
    poisoned_out["human_label"] = 1.0
    poisoned_out["rubric"] = 10
    b = score_output(poisoned_obj, poisoned_out)
    return a["score"] == b["score"] and a["components"] == b["components"]


def heading(validated: bool) -> str:
    if validated:
        return (
            "VERIFIED: completeness_score is min of three declared-coverage "
            "ratios; held-out Spearman interval supports gating at 0.90 on this gold set."
        )
    return (
        "UNVERIFIED: completeness_score must not appear in a stopping rule; "
        "spec example unique_ideas >= 100 AND completeness_score >= 0.90 is under-specified."
    )


def snapshot() -> dict[str, Any]:
    rows = per_case_rows()
    corr = correlation_report(rows)
    states = both_states(rows)
    empty = empty_objective_control()
    validated = bool(corr["validated"] and states["complete_reaches_threshold"] and states["padded_below_threshold"])
    return {
        "rows": rows,
        "correlation": corr,
        "both_states": states,
        "empty_objective": empty,
        "scorer_ignores_labels": scorer_ignores_labels(),
        "validated": validated,
        "may_bind_stopping_rule": validated,
        "heading": heading(validated),
    }


def dump_gold_json() -> Path:
    path = HERE / "gold_set.json"
    G.dump_gold(path)
    return path
