"""Paired generated-vs-baseline comparison on the frozen 20-claim corpus."""
from __future__ import annotations

import hashlib
import json
from typing import Callable

from claims import CLAIMS
from corpus import get_corpus
from generator import (
    baseline_queries,
    generate,
    generate_independent,
    lexical_terms,
    query_strings,
)

RESULT_BUDGET = 10
BACKEND = "local-snapshot-index"


def claims_sha256() -> str:
    blob = json.dumps(CLAIMS, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _merge_results(
    query_rows: list[dict[str, str]],
    searcher: Callable[[list[str], int], list[tuple[str, float]]],
    k: int = RESULT_BUDGET,
) -> list[dict]:
    best: dict[str, dict] = {}
    for row in query_rows:
        terms = lexical_terms(row["query"])
        for doc_id, score in searcher(terms, k):
            prev = best.get(doc_id)
            if prev is None or score > prev["score"]:
                best[doc_id] = {
                    "doc_id": doc_id,
                    "score": score,
                    "query": row["query"],
                    "family": row["family"],
                }
    ranked = sorted(best.values(), key=lambda r: (-r["score"], r["doc_id"]))
    return ranked[:k]


def _surface(results: list[dict], gold: set[str]) -> list[str]:
    return [r["doc_id"] for r in results if r["doc_id"] in gold]


def run_arm(
    claim: dict,
    query_rows: list[dict[str, str]],
    ranker: str,
    mutant: str | None,
) -> dict:
    corpus = get_corpus()
    gold = set(claim.get("contradicting_docs") or [])
    if ranker == "boolean":
        searcher = corpus.search_boolean
    else:
        searcher = corpus.search_bm25
    results = _merge_results(query_rows, searcher)
    hits = _surface(results, gold)
    surfaced = len(hits) > 0
    if mutant == "always-contradiction":
        surfaced = True
        hits = list(gold) or ["forced-contradiction"]
    elif mutant == "all-silent":
        surfaced = False
        hits = []
    return {
        "queries": query_strings(query_rows),
        "query_count": len(query_rows),
        "results": [
            {
                "doc_id": r["doc_id"],
                "score": round(float(r["score"]), 6),
                "query": r["query"],
                "family": r["family"],
            }
            for r in results
        ],
        "result_count": len(results),
        "contradiction_docs": hits,
        "contradiction_surfaced": surfaced,
    }


def compare_claim(
    claim: dict,
    generator: str = "v1",
    ranker: str = "bm25",
    mutant: str | None = None,
) -> dict:
    gen_fn = generate_independent if generator == "v2" else generate
    gen_arm = run_arm(claim, gen_fn(claim["text"]), ranker, mutant)
    base_arm = run_arm(claim, baseline_queries(claim["text"]), ranker, mutant)
    return {
        "id": claim["id"],
        "control": bool(claim["control"]),
        "label": claim["label"],
        "text": claim["text"],
        "generated": gen_arm,
        "baseline": base_arm,
        "generated_hit": int(gen_arm["contradiction_surfaced"]),
        "baseline_hit": int(base_arm["contradiction_surfaced"]),
        "difference": int(gen_arm["contradiction_surfaced"])
        - int(base_arm["contradiction_surfaced"]),
    }


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    false_rows = [r for r in rows if not r["control"]]
    true_rows = [r for r in rows if r["control"]]
    g_all = sum(r["generated_hit"] for r in rows)
    b_all = sum(r["baseline_hit"] for r in rows)
    g_false = sum(r["generated_hit"] for r in false_rows)
    b_false = sum(r["baseline_hit"] for r in false_rows)
    g_true = sum(r["generated_hit"] for r in true_rows)
    b_true = sum(r["baseline_hit"] for r in true_rows)
    return {
        "claim_count": n,
        "false_claim_count": len(false_rows),
        "negative_control_count": len(true_rows),
        "generated_surface_count_all": g_all,
        "baseline_surface_count_all": b_all,
        "generated_rate_all": g_all / n if n else 0.0,
        "baseline_rate_all": b_all / n if n else 0.0,
        "rate_difference_all": (g_all - b_all) / n if n else 0.0,
        "generated_surface_count_false_claims": g_false,
        "baseline_surface_count_false_claims": b_false,
        "generated_rate_false_claims": g_false / len(false_rows) if false_rows else 0.0,
        "baseline_rate_false_claims": b_false / len(false_rows) if false_rows else 0.0,
        "rate_difference_false_claims": (g_false - b_false) / len(false_rows)
        if false_rows
        else 0.0,
        "negative_control_generated_hits": g_true,
        "negative_control_baseline_hits": b_true,
        "higher_rate": g_false > b_false,
    }


def run_comparison(
    generator: str = "v1",
    ranker: str = "bm25",
    mutant: str | None = None,
) -> dict:
    rows = [
        compare_claim(c, generator=generator, ranker=ranker, mutant=mutant)
        for c in CLAIMS
    ]
    summary = summarize(rows)
    return {
        "backend": BACKEND,
        "result_budget": RESULT_BUDGET,
        "generator": generator,
        "ranker": ranker,
        "mutant": mutant or "none",
        "claims_sha256": claims_sha256(),
        "summary": summary,
        "rows": rows,
    }
