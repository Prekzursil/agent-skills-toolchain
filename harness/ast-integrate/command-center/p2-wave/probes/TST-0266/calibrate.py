#!/usr/bin/env python3
"""Tune thresholds on the tune half only; score held-out and adversarial slices."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gold import dump_gold, load_gold
from kappa import accuracy, agreement_table, bootstrap_ci, cohen_kappa
from novelty_runtime import (
    KAPPA_FLOOR,
    apply_novelty_to_stop_expression,
    classify_pair,
    seeded_broken_predictions,
    stopping_rule_from_kappa,
)

HERE = Path(__file__).resolve().parent
THRESH_PATH = HERE / "fixtures" / "thresholds.json"


def _split(rows: list[dict], name: str) -> list[dict]:
    return [r for r in rows if r.get("split") == name]


def _labels(rows: list[dict]) -> list[str]:
    return [r["label"] for r in rows]


def _preds(rows: list[dict], t_dup: float, t_var: float) -> list[str]:
    return [classify_pair(r["idea_a"], r["idea_b"], t_dup, t_var) for r in rows]


def tune_thresholds(tune_rows: list[dict]) -> dict[str, Any]:
    """Grid-search Jaccard cut-points on the TUNE half only."""
    best: dict[str, Any] | None = None
    t_dup_grid = [i / 100.0 for i in range(45, 96, 5)]
    t_var_grid = [i / 100.0 for i in range(15, 90, 5)]
    y_true = _labels(tune_rows)
    for t_dup in t_dup_grid:
        for t_var in t_var_grid:
            if t_var >= t_dup:
                continue
            y_pred = _preds(tune_rows, t_dup, t_var)
            kap = cohen_kappa(y_true, y_pred)
            acc = accuracy(y_true, y_pred)
            rec = {
                "t_dup": t_dup,
                "t_var": t_var,
                "tune_kappa": kap,
                "tune_accuracy": acc,
            }
            if best is None:
                best = rec
                continue
            if (kap, acc) > (best["tune_kappa"], best["tune_accuracy"]):
                best = rec
    if best is None:
        raise RuntimeError("empty threshold grid")
    return best


def slice_metrics(rows: list[dict], t_dup: float, t_var: float, seed: int) -> dict[str, Any]:
    y_true = _labels(rows)
    y_pred = _preds(rows, t_dup, t_var)
    table = agreement_table(y_true, y_pred)
    boot = bootstrap_ci(y_true, y_pred)
    per_case = []
    for row, pred in zip(rows, y_pred):
        per_case.append(
            {
                "id": row["id"],
                "label": row["label"],
                "predicted": pred,
                "match": row["label"] == pred,
                "adversarial": bool(row.get("adversarial")),
                "split": row.get("split"),
                "idea_a": row["idea_a"],
                "idea_b": row["idea_b"],
                "qualifier_note": row.get("qualifier_note") or "",
            }
        )
    return {
        "n": len(rows),
        "kappa": table["kappa"],
        "observed_agreement": table["observed_agreement"],
        "expected_agreement": table["expected_agreement"],
        "confusion": table["matrix"],
        "labels": table["labels"],
        "accuracy": accuracy(y_true, y_pred),
        "ci": boot,
        "per_case": per_case,
        "bootstrap_seed": seed,
    }


def adversarial_metrics(rows: list[dict], t_dup: float, t_var: float) -> dict[str, Any]:
    adv = [r for r in rows if r.get("adversarial")]
    if not adv:
        raise RuntimeError("no adversarial pairs")
    y_pred = _preds(adv, t_dup, t_var)
    distinct_recall = sum(1 for p in y_pred if p == "distinct") / len(adv)
    return {
        "n": len(adv),
        "true_label": "distinct",
        "predicted_distinct": sum(1 for p in y_pred if p == "distinct"),
        "recall_distinct": distinct_recall,
        "misclassified": [
            {"id": r["id"], "predicted": p, "qualifier_note": r.get("qualifier_note")}
            for r, p in zip(adv, y_pred)
            if p != "distinct"
        ],
        "note": (
            "All-true-class kappa is degenerate on this slice; report distinct-recall "
            "instead of kappa."
        ),
    }


def demotion_controls(heldout: list[dict], heldout_kappa: float) -> dict[str, Any]:
    floor = KAPPA_FLOOR
    live_gate = stopping_rule_from_kappa(heldout_kappa, floor)
    live_stop = apply_novelty_to_stop_expression(
        {"predicate": "unique_ideas >= 100 AND novelty_score >= 0.8", "uses_novelty_score": True},
        heldout_kappa,
        floor,
    )
    y_true = _labels(heldout)
    broken = seeded_broken_predictions(y_true, seed=26601)
    broken_kappa = cohen_kappa(y_true, broken)
    broken_gate = stopping_rule_from_kappa(broken_kappa, floor)
    broken_stop = apply_novelty_to_stop_expression(
        {"predicate": "unique_ideas >= 100 AND novelty_score >= 0.8", "uses_novelty_score": True},
        broken_kappa,
        floor,
    )
    perfect_gate = stopping_rule_from_kappa(1.0, floor)
    perfect_stop = apply_novelty_to_stop_expression(
        {"predicate": "unique_ideas >= 100 AND novelty_score >= 0.8", "uses_novelty_score": True},
        1.0,
        floor,
    )
    fired = (
        broken_gate["may_gate_stopping_rule"] is False
        and broken_stop["accepted"] is False
        and broken_kappa < floor
    )
    silent_on_perfect = (
        perfect_gate["may_gate_stopping_rule"] is True and perfect_stop["accepted"] is True
    )
    return {
        "floor": floor,
        "live": {"gate": live_gate, "stop": live_stop},
        "seeded_below_floor": {
            "seed": 26601,
            "kappa": broken_kappa,
            "gate": broken_gate,
            "stop": broken_stop,
            "predictions": broken,
            "fired": fired,
        },
        "perfect_agreement_control": {
            "kappa": 1.0,
            "gate": perfect_gate,
            "stop": perfect_stop,
            "demotion_silent": silent_on_perfect,
        },
        "demotion_fires_on_seeded_below_floor": fired,
        "demotion_silent_on_perfect": silent_on_perfect,
    }


def run_calibration() -> dict[str, Any]:
    dump_gold()
    gold = load_gold()
    rows = gold["pairs"]
    tune_rows = _split(rows, "tune")
    held_rows = _split(rows, "heldout")
    if len(tune_rows) != 30 or len(held_rows) != 30:
        raise RuntimeError(f"split sizes tune={len(tune_rows)} heldout={len(held_rows)}")
    if gold["kappa_floor_preregistered"] != KAPPA_FLOOR:
        raise RuntimeError("gold-set floor drifted from runtime constant")
    chosen = tune_thresholds(tune_rows)
    t_dup, t_var = chosen["t_dup"], chosen["t_var"]
    THRESH_PATH.parent.mkdir(parents=True, exist_ok=True)
    THRESH_PATH.write_text(
        json.dumps(
            {
                "t_dup": t_dup,
                "t_var": t_var,
                "tuned_on": "tune",
                "tune_n": len(tune_rows),
                "kappa_floor": KAPPA_FLOOR,
                "tune_kappa": chosen["tune_kappa"],
                "tune_accuracy": chosen["tune_accuracy"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    held = slice_metrics(held_rows, t_dup, t_var, seed=266)
    tune = slice_metrics(tune_rows, t_dup, t_var, seed=266)
    adv_all = adversarial_metrics(rows, t_dup, t_var)
    adv_held = adversarial_metrics(held_rows, t_dup, t_var)
    demo = demotion_controls(held_rows, held["kappa"])
    return {
        "gold": gold,
        "thresholds": {"t_dup": t_dup, "t_var": t_var, **chosen},
        "tune": tune,
        "heldout": held,
        "adversarial_all": adv_all,
        "adversarial_heldout": adv_held,
        "demotion": demo,
        "kappa_floor": KAPPA_FLOOR,
    }


if __name__ == "__main__":
    result = run_calibration()
    h = result["heldout"]
    print(
        json.dumps(
            {
                "tune_kappa": result["thresholds"]["tune_kappa"],
                "heldout_kappa": h["kappa"],
                "heldout_ci": [h["ci"]["ci_low"], h["ci"]["ci_high"]],
                "heldout_n": h["n"],
                "t_dup": result["thresholds"]["t_dup"],
                "t_var": result["thresholds"]["t_var"],
                "adv_recall_all": result["adversarial_all"]["recall_distinct"],
                "adv_recall_heldout": result["adversarial_heldout"]["recall_distinct"],
                "demotion_fired": result["demotion"]["demotion_fires_on_seeded_below_floor"],
            },
            indent=2,
            sort_keys=True,
        )
    )
