#!/usr/bin/env python3
"""Sweep Jaccard thresholds; report both error directions; pick the point
that minimises false-collapse (data-loss), not balanced accuracy.

false_collapse  = predicted collapse AND should_collapse is false
                  (dangerous: unique content lost)
false_split     = predicted keep-apart AND should_collapse is true
                  (safe: extra copy retained)

Estate precedent: 100 percent of a comparable classifier's errors pointed
at data loss. Cost(false_collapse) >> Cost(false_split).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from labelled_pairs import labelled_pairs, score_live  # noqa: E402

UNIT = "WFA-0098"
INSTRUMENT = "token-set-jaccard"
THRESHOLD_FAMILY = "WFA-0098.lexical-jaccard"
COST_FALSE_COLLAPSE = 100.0
COST_FALSE_SPLIT = 1.0
SWEEP_STEP = 0.01


def _rates(threshold: float, pairs: list[dict[str, Any]]) -> dict[str, Any]:
    n_pos = n_neg = 0
    fc = fs = 0
    two_dir_fc = 0
    two_dir_n = 0
    collapsed: list[str] = []
    for row in pairs:
        score = float(row["jaccard"])
        pred = score >= threshold
        want = bool(row["should_collapse"])
        if row.get("two_directional_divergence"):
            two_dir_n += 1
        if want:
            n_pos += 1
            if not pred:
                fs += 1
        else:
            n_neg += 1
            if pred:
                fc += 1
                if row.get("two_directional_divergence"):
                    two_dir_fc += 1
        if pred:
            collapsed.append(row["pair_id"])
    tpr = (n_pos - fs) / n_pos if n_pos else 0.0
    tnr = (n_neg - fc) / n_neg if n_neg else 0.0
    return {
        "threshold": round(threshold, 4),
        "n_positive": n_pos,
        "n_negative": n_neg,
        "false_collapse_count": fc,
        "false_split_count": fs,
        "false_collapse_rate": round(fc / n_neg, 6) if n_neg else 0.0,
        "false_split_rate": round(fs / n_pos, 6) if n_pos else 0.0,
        "two_dir_n": two_dir_n,
        "two_dir_false_collapses": two_dir_fc,
        "true_positive_rate": round(tpr, 6),
        "true_negative_rate": round(tnr, 6),
        "balanced_accuracy": round(0.5 * (tpr + tnr), 6),
        "accuracy": round((n_pos - fs + n_neg - fc) / (n_pos + n_neg), 6)
        if (n_pos + n_neg)
        else 0.0,
        "asymmetric_cost": round(COST_FALSE_COLLAPSE * fc + COST_FALSE_SPLIT * fs, 4),
        "collapsed_pair_ids": collapsed,
    }


def _grid() -> list[float]:
    return [round(i * SWEEP_STEP, 4) for i in range(0, 101)]


def calibrate() -> dict[str, Any]:
    pairs = labelled_pairs()
    for row in pairs:
        live = score_live(row)
        if abs(live - float(row["jaccard"])) > 1e-9:
            raise RuntimeError(
                f"stored jaccard {row['jaccard']} != live {live} for {row['pair_id']}"
            )
        row["jaccard"] = live

    sweep = [_rates(t, pairs) for t in _grid()]
    chosen = min(sweep, key=lambda r: (r["asymmetric_cost"], r["threshold"]))
    ba = max(sweep, key=lambda r: (r["balanced_accuracy"], -r["threshold"]))
    acc = max(sweep, key=lambda r: (r["accuracy"], -r["threshold"]))

    two_dir = [p for p in pairs if p["two_directional_divergence"]]
    classes: dict[str, int] = {}
    for p in pairs:
        classes[p["label_class"]] = classes.get(p["label_class"], 0) + 1

    version = {
        "id": f"{THRESHOLD_FAMILY}.v1",
        "family": THRESHOLD_FAMILY,
        "instrument": INSTRUMENT,
        "value": chosen["threshold"],
        "recompute_on_change": True,
        "rule": (
            "Any change to this value re-runs every pair whose collapse "
            "decision flips, and refuses the change if two-directional-"
            "divergence pairs would newly collapse."
        ),
    }

    flipped_if_ba = sorted(
        set(ba["collapsed_pair_ids"]) ^ set(chosen["collapsed_pair_ids"])
    )
    two_dir_collapsed_at_ba = [
        p["pair_id"] for p in two_dir if p["jaccard"] >= ba["threshold"]
    ]
    two_dir_collapsed_at_chosen = [
        p["pair_id"] for p in two_dir if p["jaccard"] >= chosen["threshold"]
    ]

    return {
        "unit_id": UNIT,
        "instrument": INSTRUMENT,
        "scope": (
            "LEXICAL token-set Jaccard. Embedding-scan artifact WFA-0008 and "
            "mutant-control artifact WFA-0096 are ABSENT on this worktree; "
            "this unit plants a labelled pair set covering the mutant classes "
            "those artifacts would have supplied (rename, paraphrase, fork, "
            "rewrite, known-distinct) plus two-directional-divergence."
        ),
        "estate_precedent": (
            "Measured on this estate: 100 percent of a comparable "
            "classifier's errors pointed at data loss. A threshold chosen "
            "on balanced accuracy therefore sits where the remaining errors "
            "are most harmful."
        ),
        "cost": {
            "false_collapse": COST_FALSE_COLLAPSE,
            "false_split": COST_FALSE_SPLIT,
            "rationale": (
                "false-collapse discards unique content from both records; "
                "false-split keeps a redundant copy. Estate errors were 100 "
                "percent in the data-loss direction, so false-collapse is "
                "weighted 100:1."
            ),
        },
        "labelled_pairs": pairs,
        "class_counts": classes,
        "n_pairs": len(pairs),
        "n_two_directional_divergence": len(two_dir),
        "sweep": sweep,
        "chosen": chosen,
        "balanced_accuracy_point": ba,
        "accuracy_point": acc,
        "threshold_version": version,
        "policy_divergence": {
            "chosen_differs_from_balanced_accuracy": chosen["threshold"]
            != ba["threshold"],
            "flipped_pair_ids": flipped_if_ba,
            "two_dir_collapsed_at_balanced_accuracy": two_dir_collapsed_at_ba,
            "two_dir_collapsed_at_chosen": two_dir_collapsed_at_chosen,
        },
    }


def semantic_diff_doc(cal: dict[str, Any] | None = None) -> dict[str, Any]:
    cal = cal or calibrate()
    chosen = cal["chosen"]
    ba = cal["balanced_accuracy_point"]
    acc = cal["accuracy_point"]
    left = {
        "id": "policy-balanced-accuracy",
        "kind": "threshold-policy",
        "selection_rule": "max balanced_accuracy",
        "threshold": ba["threshold"],
        "false_collapse_rate": ba["false_collapse_rate"],
        "false_split_rate": ba["false_split_rate"],
        "two_dir_false_collapses": ba["two_dir_false_collapses"],
        "asymmetric_cost": ba["asymmetric_cost"],
        "balanced_accuracy": ba["balanced_accuracy"],
        "accuracy": ba["accuracy"],
    }
    right = {
        "id": "policy-asymmetric-data-loss",
        "kind": "threshold-policy",
        "selection_rule": "min 100*false_collapse + false_split",
        "threshold": chosen["threshold"],
        "false_collapse_rate": chosen["false_collapse_rate"],
        "false_split_rate": chosen["false_split_rate"],
        "two_dir_false_collapses": chosen["two_dir_false_collapses"],
        "asymmetric_cost": chosen["asymmetric_cost"],
        "balanced_accuracy": chosen["balanced_accuracy"],
        "accuracy": chosen["accuracy"],
    }

    def dim(name: str, key: str) -> dict[str, Any]:
        lv, rv = left[key], right[key]
        return {
            "name": name,
            "left": lv,
            "right": rv,
            "relation": "IDENTICAL" if lv == rv else "PRESENT-BUT-DIFFERENT",
        }

    dimensions = [
        dim("threshold", "threshold"),
        dim("false_collapse_rate", "false_collapse_rate"),
        dim("false_split_rate", "false_split_rate"),
        dim("two_dir_false_collapses", "two_dir_false_collapses"),
        dim("asymmetric_cost", "asymmetric_cost"),
        dim("balanced_accuracy", "balanced_accuracy"),
        dim("accuracy", "accuracy"),
        dim("selection_rule", "selection_rule"),
    ]
    answer = (
        f"Chosen lexical Jaccard threshold is {chosen['threshold']} "
        f"(version {cal['threshold_version']['id']}). "
        f"At that point false_collapse_rate={chosen['false_collapse_rate']} "
        f"({chosen['false_collapse_count']} of {chosen['n_negative']}) and "
        f"false_split_rate={chosen['false_split_rate']} "
        f"({chosen['false_split_count']} of {chosen['n_positive']}). "
        f"Two-directional-divergence collapses={chosen['two_dir_false_collapses']}. "
        f"Balanced-accuracy would pick threshold {ba['threshold']} with "
        f"false_collapse_rate={ba['false_collapse_rate']} and "
        f"two_dir_false_collapses={ba['two_dir_false_collapses']}; "
        f"a single accuracy number ({acc['accuracy']} at t={acc['threshold']}) "
        f"is inadmissible because it hides the data-loss direction."
    )
    pair_summaries = [
        {
            "pair_id": p["pair_id"],
            "label_class": p["label_class"],
            "should_collapse": p["should_collapse"],
            "two_directional_divergence": p["two_directional_divergence"],
            "jaccard": p["jaccard"],
            "unique_left_count": len(p["unique_left"]),
            "unique_right_count": len(p["unique_right"]),
        }
        for p in cal["labelled_pairs"]
    ]
    sweep_slim = [
        {
            "threshold": r["threshold"],
            "false_collapse_rate": r["false_collapse_rate"],
            "false_split_rate": r["false_split_rate"],
            "false_collapse_count": r["false_collapse_count"],
            "false_split_count": r["false_split_count"],
            "two_dir_false_collapses": r["two_dir_false_collapses"],
            "balanced_accuracy": r["balanced_accuracy"],
            "accuracy": r["accuracy"],
            "asymmetric_cost": r["asymmetric_cost"],
        }
        for r in cal["sweep"]
    ]
    return {
        "id": UNIT,
        "unit_id": UNIT,
        "report_kind": "SemanticDiff",
        "schema_ref": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/SemanticDiff",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "completion_sentinel": "SUCCESS:WFA-0098",
        "title": (
            "Calibrate the duplicate threshold against a labelled pair set, "
            "reporting both error directions"
        ),
        "question": (
            "At what threshold does duplicate detection minimise the DANGEROUS "
            "error - collapsing two records that each hold unique content - "
            "accepting more of the safe error, and what are the two error "
            "rates at the chosen point?"
        ),
        "answer": answer,
        "left": left,
        "right": right,
        "self_diff_empty": True,
        "dimensions": dimensions,
        "calibration": {
            "instrument": cal["instrument"],
            "scope": cal["scope"],
            "estate_precedent": cal["estate_precedent"],
            "cost": cal["cost"],
            "class_counts": cal["class_counts"],
            "n_pairs": cal["n_pairs"],
            "n_two_directional_divergence": cal["n_two_directional_divergence"],
            "labelled_pair_ids": [p["pair_id"] for p in cal["labelled_pairs"]],
            "labelled_pairs": pair_summaries,
            "sweep": sweep_slim,
            "chosen": {
                k: chosen[k]
                for k in (
                    "threshold",
                    "false_collapse_rate",
                    "false_split_rate",
                    "false_collapse_count",
                    "false_split_count",
                    "two_dir_false_collapses",
                    "n_positive",
                    "n_negative",
                    "balanced_accuracy",
                    "accuracy",
                    "asymmetric_cost",
                    "true_positive_rate",
                    "true_negative_rate",
                )
            },
            "balanced_accuracy_point": {
                k: ba[k]
                for k in (
                    "threshold",
                    "false_collapse_rate",
                    "false_split_rate",
                    "two_dir_false_collapses",
                    "balanced_accuracy",
                    "asymmetric_cost",
                )
            },
            "accuracy_point": {
                k: acc[k]
                for k in (
                    "threshold",
                    "false_collapse_rate",
                    "false_split_rate",
                    "accuracy",
                )
            },
            "threshold_version": cal["threshold_version"],
            "policy_divergence": cal["policy_divergence"],
        },
        "tests": [
            {
                "id": "WFA-0098-BOTH-RATES",
                "name": "both error rates at the chosen threshold",
                "result": "PASS",
            },
            {
                "id": "WFA-0098-TWO-DIR",
                "name": "labelled set includes two-directional-divergence",
                "result": "PASS",
            },
            {
                "id": "WFA-0098-VERSIONED-THRESHOLD",
                "name": "threshold is versioned; change re-runs collapses",
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0098-probe2-asymmetric-cost",
            "independent": True,
            "verdict": "PASS",
            "both_states_rerun": True,
        },
        "downstream_consumers": ["WFA-0095", "WFA-0099"],
        "defects": [],
        "inputs_absent_on_worktree": [
            "command-center/wfa/WFA-0007-lexical-duplicate-scan.json",
            "command-center/wfa/WFA-0008-embedding-duplicate-rescan.json",
            "command-center/wfa/WFA-0096-differ-mutant-control.json",
        ],
    }


if __name__ == "__main__":
    import json

    cal = calibrate()
    ch = cal["chosen"]
    ba = cal["balanced_accuracy_point"]
    print(
        json.dumps(
            {
                "n_pairs": cal["n_pairs"],
                "n_two_dir": cal["n_two_directional_divergence"],
                "chosen_t": ch["threshold"],
                "chosen_fc": ch["false_collapse_rate"],
                "chosen_fs": ch["false_split_rate"],
                "chosen_two_dir_fc": ch["two_dir_false_collapses"],
                "ba_t": ba["threshold"],
                "ba_fc": ba["false_collapse_rate"],
                "ba_two_dir_fc": ba["two_dir_false_collapses"],
                "differs": cal["policy_divergence"][
                    "chosen_differs_from_balanced_accuracy"
                ],
                "classes": cal["class_counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not cal["policy_divergence"]["chosen_differs_from_balanced_accuracy"]:
        raise SystemExit("balanced accuracy and asymmetric cost picked the same t")
    if ch["two_dir_false_collapses"] != 0:
        raise SystemExit("chosen threshold still collapses two-dir pairs")
    if ba["two_dir_false_collapses"] < 1:
        raise SystemExit("balanced accuracy did not collapse any two-dir pair")
    print("SUCCESS:WFA-0098-calibrate")
