#!/usr/bin/env python3
"""Score the planted pair table and classify each method on both-states."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import methods as M

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "planted_claims.json"

MERGE_CLASSES = (
    "exact_rename",
    "paraphrase",
    "one_parameter_fork",
    "full_rewrite",
)
BOTH_STATES_POSITIVE = "paraphrase"
BOTH_STATES_NEGATIVE = "true_distinction"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def by_id(fixture: dict) -> dict[str, dict]:
    return {c["id"]: c for c in fixture["claims"]}


def pair_rows(fixture: dict | None = None) -> list[dict]:
    fixture = fixture or load_fixture()
    index = by_id(fixture)
    rows = []
    for spec in fixture["labeled_pairs"]:
        left = index[spec["left"]]
        right = index[spec["right"]]
        scores = M.pairwise_named(left, right)
        scores.update(
            {
                "class": spec["class"],
                "intended": spec["intended"],
                "should_merge": spec["intended"] == "SAME",
            }
        )
        rows.append(scores)
    return rows


def method_report(rows: list[dict], method_id: str) -> dict:
    field = M.method_merge_field(method_id)
    per_class: dict[str, dict] = {}
    for cls in (*MERGE_CLASSES, BOTH_STATES_NEGATIVE):
        planted = [r for r in rows if r["class"] == cls]
        if not planted:
            continue
        merged = [r for r in planted if r[field]]
        per_class[cls] = {
            "planted": len(planted),
            "merged": len(merged),
            "recall": (len(merged) / len(planted)) if planted else None,
        }
    para = [r for r in rows if r["class"] == BOTH_STATES_POSITIVE]
    dist = [r for r in rows if r["class"] == BOTH_STATES_NEGATIVE]
    all_para = bool(para) and all(r[field] for r in para)
    any_dist = any(r[field] for r in dist)
    zero_dist = not any_dist
    label = M.taxonomy(all_para, any_dist)
    tp = sum(1 for r in rows if r["should_merge"] and r[field])
    fp = sum(1 for r in rows if (not r["should_merge"]) and r[field])
    fn = sum(1 for r in rows if r["should_merge"] and not r[field])
    tn = sum(1 for r in rows if (not r["should_merge"]) and not r[field])
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    return {
        "method": method_id,
        "taxonomy": label,
        "all_paraphrases_merged": all_para,
        "any_true_distinction_merged": any_dist,
        "all_true_distinctions_kept": zero_dist,
        "both_states_pass": label == "correct",
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision": round(prec, 6),
        "recall": round(rec, 6),
        "per_class": per_class,
    }


def evaluate(fixture: dict | None = None) -> dict:
    fixture = fixture or load_fixture()
    rows = pair_rows(fixture)
    named = {mid: method_report(rows, mid) for mid in M.named_method_ids()}
    controls = {mid: method_report(rows, mid) for mid in M.control_method_ids()}
    winners = [
        mid
        for mid, rep in named.items()
        if rep["both_states_pass"]
        and rep["per_class"].get("full_rewrite", {}).get("merged")
        == rep["per_class"].get("full_rewrite", {}).get("planted")
    ]
    return {
        "unit_id": "RES-0173",
        "jaccard_threshold": M.JACCARD_THRESHOLD,
        "cosine_threshold": M.COSINE_THRESHOLD,
        "embedding_kind": "seeded-random-indexing-mean-pool",
        "embedding_dim": M.EMBED_DIM,
        "embedding_seed": M.EMBED_SEED,
        "neural_sentence_embedding": "NOT-CHECKED",
        "n_labeled_pairs": len(rows),
        "pair_rows": rows,
        "named_methods": named,
        "controls": controls,
        "methods_both_states_correct": [
            mid for mid, rep in named.items() if rep["both_states_pass"]
        ],
        "methods_both_states_and_rewrite": winners,
        "headline_method": "mechanism_key" if "mechanism_key" in winners else None,
    }


def assert_invariants(report: dict) -> None:
    rows = report["pair_rows"]
    para = [r for r in rows if r["class"] == "paraphrase"]
    dist = [r for r in rows if r["class"] == "true_distinction"]
    rew = [r for r in rows if r["class"] == "full_rewrite"]
    if len(para) < 2:
        raise AssertionError("need at least two planted paraphrases")
    if len(dist) < 2:
        raise AssertionError("need at least two planted true distinctions")
    if len(rew) < 1:
        raise AssertionError("need a planted full rewrite")
    for r in para:
        if r["jaccard"] < M.JACCARD_THRESHOLD:
            raise AssertionError(
                f"paraphrase {r['left']}/{r['right']} jaccard={r['jaccard']} "
                "is below the a priori 0.50; fixture is not a lexical paraphrase"
            )
    for r in dist:
        if r["jaccard"] >= M.JACCARD_THRESHOLD:
            raise AssertionError(
                f"true distinction {r['left']}/{r['right']} jaccard={r['jaccard']} "
                "is not lexically distinct"
            )
    for r in rew:
        if r["jaccard"] >= M.JACCARD_THRESHOLD:
            raise AssertionError("full_rewrite is not a rewrite (Jaccard too high)")
        if r["lexical_jaccard_merge"]:
            raise AssertionError("full_rewrite was merged by Jaccard")
        if not r["mechanism_key_merge"]:
            raise AssertionError("full_rewrite missed by mechanism key")
    ctrl = report["controls"]
    if ctrl["always_merge"]["taxonomy"] != "collapser":
        raise AssertionError("always-merge control is not classified as collapser")
    if ctrl["exact_string"]["taxonomy"] != "string_comparator":
        raise AssertionError("exact-string control is not classified as string_comparator")
    key = report["named_methods"]["mechanism_key"]
    if not key["both_states_pass"]:
        raise AssertionError("mechanism_key failed both-states")
    if key["per_class"]["full_rewrite"]["merged"] != key["per_class"]["full_rewrite"]["planted"]:
        raise AssertionError("mechanism_key missed a rewrite")
    jac = report["named_methods"]["lexical_jaccard"]
    if not jac["both_states_pass"]:
        raise AssertionError("lexical Jaccard failed paraphrase/distinction both-states")
    if jac["per_class"]["full_rewrite"]["merged"] != 0:
        raise AssertionError("lexical Jaccard unexpectedly merged a rewrite")
    if report["headline_method"] != "mechanism_key":
        raise AssertionError("headline_method is not mechanism_key")
    if report["neural_sentence_embedding"] != "NOT-CHECKED":
        raise AssertionError("neural embedding was claimed without a runtime")


def main() -> int:
    report = evaluate()
    assert_invariants(report)
    print(json.dumps(
        {
            "named": {k: {
                "taxonomy": v["taxonomy"],
                "precision": v["precision"],
                "recall": v["recall"],
                "per_class": v["per_class"],
            } for k, v in report["named_methods"].items()},
            "controls": {k: v["taxonomy"] for k, v in report["controls"].items()},
            "headline": report["headline_method"],
        },
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
