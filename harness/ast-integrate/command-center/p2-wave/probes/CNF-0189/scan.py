#!/usr/bin/env python3
"""Pairwise lexical + embedding scan with planted-calibrated thresholds."""
from __future__ import annotations

from typing import Any

import catalog as C
import planted
import similarity as S

LEX_THRESHOLD = 0.50
DEEP_JACCARD_MAX = 0.24
DEEP_JACCARD_MIN = 0.05
DEEP_JACCARD_MAX = DEEP_JACCARD_MAX
DEEP_JACCARD_MIN = DEEP_JACCARD_MIN


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


_pair_key = _pair_key


def planted_control_pairs() -> list[dict[str, Any]]:
    recs = {r["id"]: r for r in planted.records()}
    seed = recs[planted.SEED_ID]
    seed_text = S.body_of(seed)
    rows: list[dict[str, Any]] = []
    for rec in recs.values():
        if rec["id"] == planted.SEED_ID:
            continue
        other = S.body_of(rec)
        jac = S.jaccard(seed_text, other)
        cos = S.cosine_texts(seed_text, other)
        cls = rec.get("mutant_class") or rec.get("mutant_class")
        rows.append(
            {
                "id_a": planted.SEED_ID,
                "id_b": rec["id"],
                "mutant_class": cls,
                "jaccard": round(jac, 6),
                "cosine": round(cos, 6),
                "expect_duplicate": cls in planted.NEAR_DUP_CLASSES,
            }
        )
    return rows


def calibrate(control_rows: list[dict[str, Any]]) -> dict[str, Any]:
    dup_cos = [r["cosine"] for r in control_rows if r["expect_duplicate"]]
    dist_cos = [r["cosine"] for r in control_rows if not r["expect_duplicate"]]
    if not dup_cos or not dist_cos:
        raise SystemExit("FAILED:CNF-0189 calibration missing planted classes")
    min_dup = min(dup_cos)
    max_dist = max(dist_cos)
    if min_dup <= max_dist:
        raise SystemExit(
            f"FAILED:CNF-0189 embedding not separable min_dup={min_dup} max_dist={max_dist}"
        )
    threshold = (min_dup + max_dist) / 2.0
    return {
        "embedding_threshold": round(threshold, 6),
        "lexical_threshold": LEX_THRESHOLD,
        "min_duplicate_cosine": round(min_dup, 6),
        "max_distinct_cosine": round(max_dist, 6),
        "justification": (
            "Embedding threshold is the midpoint between the lowest cosine among "
            "planted duplicates (rename, one-parameter, surface, deep paraphrase) "
            f"({min_dup:.4f}) and the highest cosine among planted distinct "
            f"entries ({max_dist:.4f}). Lexical threshold stays at {LEX_THRESHOLD:.2f}, "
            "the conventional Jaccard near-duplicate cut; it is NOT moved to "
            "capture the deep paraphrase."
        ),
    }


def adjudicate(text_a: str, text_b: str) -> dict[str, Any]:
    """Read bodies via concept inventory. Does not take pair scores."""
    ca, cb = S.concept_set(text_a), S.concept_set(text_b)
    if not ca and not cb:
        return {
            "verdict": "uncertain",
            "reason": "both-empty-concept-set",
            "concept_jaccard": 0.0,
            "shared_concepts": [],
        }
    union = ca | cb
    inter = ca & cb
    cj = len(inter) / len(union) if union else 0.0
    if cj >= 0.75:
        verdict = "same_mechanism"
        reason = "concept-inventory overlap >= 0.75"
    elif cj <= 0.25:
        verdict = "distinct"
        reason = "concept-inventory overlap <= 0.25"
    else:
        verdict = "uncertain"
        reason = (
            "concept-inventory overlap in the mid band; bodies read, "
            "threshold not retuned"
        )
    return {
        "verdict": verdict,
        "reason": reason,
        "concept_jaccard": round(cj, 6),
        "shared_concepts": sorted(inter),
    }


def histogram(values: list[float], edges: list[float]) -> list[dict[str, Any]]:
    buckets = []
    for i, lo in enumerate(edges[:-1]):
        hi = edges[i + 1]
        n = sum(
            1
            for v in values
            if (v >= lo and v < hi) or (i == len(edges) - 2 and v == hi)
        )
        buckets.append({"lo": lo, "hi": hi, "count": n})
    return buckets


def run_scan() -> dict[str, Any]:
    corpus = C.load_corpus()
    records = corpus["records"]
    by_id = {r["id"]: r for r in records}
    control = planted_control_pairs()
    cal = calibrate(control)

    deep = next(r for r in control if r["mutant_class"] == "deep_paraphrase")
    distinct = next(r for r in control if r["mutant_class"] == "distinct")
    if not (DEEP_JACCARD_MIN <= deep["jaccard"] <= DEEP_JACCARD_MAX):
        raise SystemExit(
            f"FAILED:CNF-0189 deep paraphrase Jaccard {deep['jaccard']} not in 0.05-0.24"
        )
    if deep["cosine"] < cal["embedding_threshold"]:
        raise SystemExit("FAILED:CNF-0189 deep paraphrase cosine below embedding threshold")
    if distinct["cosine"] >= cal["embedding_threshold"]:
        raise SystemExit("FAILED:CNF-0189 distinct control fired embedding")
    if distinct["jaccard"] >= LEX_THRESHOLD:
        raise SystemExit("FAILED:CNF-0189 distinct control fired lexical")

    texts = {r["id"]: S.body_of(r) for r in records}
    vecs = {rid: S.embed(txt) for rid, txt in texts.items()}
    ids = [r["id"] for r in records]

    lex_hits: list[dict[str, Any]] = []
    emb_hits: list[dict[str, Any]] = []
    all_cos: list[float] = []
    all_jac: list[float] = []
    pair_n = 0
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            pair_n += 1
            jac = S.jaccard(texts[a], texts[b])
            cos = S.cosine(vecs[a], vecs[b])
            all_cos.append(cos)
            all_jac.append(jac)
            rec = {
                "id_a": a,
                "id_b": b,
                "jaccard": round(jac, 6),
                "cosine": round(cos, 6),
                "lexical_hit": jac >= cal["lexical_threshold"],
                "embedding_hit": cos >= cal["embedding_threshold"],
            }
            if rec["lexical_hit"]:
                lex_hits.append(rec)
            if rec["embedding_hit"]:
                emb_hits.append(rec)

    lex_keys = {_pair_key(p["id_a"], p["id_b"]) for p in lex_hits}
    emb_keys = {_pair_key(p["id_a"], p["id_b"]) for p in emb_hits}
    both_keys = lex_keys & emb_keys
    xor_keys = (lex_keys | emb_keys) - both_keys

    def describe(key: tuple[str, str], lexical_hit: bool, embedding_hit: bool) -> dict[str, Any]:
        a, b = key
        return {
            "id_a": a,
            "id_b": b,
            "kind_a": by_id[a].get("kind"),
            "kind_b": by_id[b].get("kind"),
            "family_a": by_id[a].get("family"),
            "family_b": by_id[b].get("family"),
            "jaccard": round(S.jaccard(texts[a], texts[b]), 6),
            "cosine": round(S.cosine(vecs[a], vecs[b]), 6),
            "lexical_hit": lexical_hit,
            "embedding_hit": embedding_hit,
        }

    both = [describe(k, True, True) for k in sorted(both_keys)]
    disagreements = []
    for k in sorted(xor_keys):
        row = describe(k, k in lex_keys, k in emb_keys)
        row["adjudication"] = adjudicate(texts[k[0]], texts[k[1]])
        disagreements.append(row)

    planted_marks = []
    for row in control:
        jac = row["jaccard"]
        if jac >= LEX_THRESHOLD:
            band = "lexical-high"
        elif jac <= DEEP_JACCARD_MAX:
            band = "lexical-blind-0.05-0.24"
        else:
            band = "lexical-mid"
        planted_marks.append(
            {
                "mutant_class": row["mutant_class"],
                "id_b": row["id_b"],
                "jaccard": jac,
                "cosine": row["cosine"],
                "band": band,
            }
        )

    return {
        "corpus": {
            "libraries_present": corpus["libraries_present"],
            "catalog_files_absent": corpus["catalog_files_absent"],
            "counts": corpus["counts"],
        },
        "calibration": cal,
        "planted_control": control,
        "planted_marked_on_distribution": planted_marks,
        "pair_count": pair_n,
        "cosine_histogram": histogram(
            all_cos, [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01]
        ),
        "jaccard_histogram": histogram(all_jac, [0.0, 0.05, 0.24, 0.5, 0.93, 1.01]),
        "high_confidence_both": both,
        "disagreement_adjudicated": disagreements,
        "lexical_hit_count": len(lex_hits),
        "embedding_hit_count": len(emb_hits),
        "both_count": len(both),
        "xor_count": len(disagreements),
    }
