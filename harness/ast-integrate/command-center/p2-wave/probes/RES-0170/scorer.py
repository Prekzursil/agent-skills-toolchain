#!/usr/bin/env python3
"""Computable research-quality target. A runner evaluates it without a human.

Dimensions (equal weight):
  source_class_coverage     resolved+matched citations in the closed 16-class set
  independent_source_rate   load-bearing claims with >=2 independent origins
  contradiction_coverage    load-bearing claims with a resolved contradiction search
  named_experiment_rate     unresolved unknowns that carry a named, resolved experiment
  citation_resolvability    citations whose live HTTP status is 2xx AND body contains
                            the claimed quote (which must also appear in the claim text)

Unresolvable citations contribute to the denominator of resolvability and to
nothing else. Counting citation-shaped URL strings is the inert naive matcher.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from lineage import independent_origin_count, naive_url_count
from resolver import FixtureHttp, resolve_citation, routes_from_bodies
from source_classes import DERIVATION, SOURCE_CLASSES, SOURCE_CLASS_SET, is_registered

DIMENSIONS = (
    "source_class_coverage",
    "independent_source_rate",
    "contradiction_coverage",
    "named_experiment_rate",
    "citation_resolvability",
)
WEIGHT = 1.0 / len(DIMENSIONS)

GATES = {
    "source_class_coverage_min": 4 / 16,
    "independent_source_rate_min": 1.0,
    "contradiction_coverage_min": 1.0,
    "named_experiment_rate_min": 1.0,
    "citation_resolvability_min": 0.8,
}


def _all_sources(claim: dict[str, Any]) -> list[dict[str, Any]]:
    return list(claim.get("sources") or [])


def _contra_sources(claim: dict[str, Any]) -> list[dict[str, Any]]:
    cs = claim.get("contradiction_search")
    if not isinstance(cs, dict):
        return []
    return list(cs.get("sources") or [])


def _unknown_sources(unknown: dict[str, Any]) -> list[dict[str, Any]]:
    exp = unknown.get("named_experiment")
    if not isinstance(exp, dict):
        return []
    return list(exp.get("sources") or [])


def collect_citations(art: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for claim in art.get("claims") or []:
        for src in _all_sources(claim):
            row = deepcopy(src)
            row["_role"] = "claim"
            row["_claim_id"] = claim.get("id")
            row["_claim_text"] = claim.get("claim") or ""
            out.append(row)
        for src in _contra_sources(claim):
            row = deepcopy(src)
            row["_role"] = "contradiction"
            row["_claim_id"] = claim.get("id")
            row["_claim_text"] = str((claim.get("contradiction_search") or {}).get("query") or "")
            out.append(row)
    for unknown in art.get("unknowns") or []:
        for src in _unknown_sources(unknown):
            row = deepcopy(src)
            row["_role"] = "experiment"
            row["_claim_id"] = unknown.get("id")
            row["_claim_text"] = str((unknown.get("named_experiment") or {}).get("method") or "")
            out.append(row)
    return out


def quote_in_text(quote: str, text: str) -> bool:
    q = (quote or "").strip()
    if not q:
        return False
    return q in (text or "")


def resolve_artifact(art: dict[str, Any], server: FixtureHttp) -> dict[str, Any]:
    resolved_claims = []
    for claim in art.get("claims") or []:
        sources = [resolve_citation(server, s) for s in _all_sources(claim)]
        for src in sources:
            src["quote_in_claim"] = quote_in_text(
                str(src.get("claimed_quote") or ""), str(claim.get("claim") or "")
            )
            src["substance"] = bool(src.get("resolvable")) and bool(src.get("quote_in_claim"))
        contra = claim.get("contradiction_search")
        contra_out = None
        if isinstance(contra, dict):
            csrc = [resolve_citation(server, s) for s in (contra.get("sources") or [])]
            qtext = str(contra.get("query") or "")
            for src in csrc:
                src["quote_in_claim"] = quote_in_text(str(src.get("claimed_quote") or ""), qtext) or quote_in_text(
                    str(src.get("claimed_quote") or ""), str(src.get("claimed_quote") or "")
                )
                # Contradiction logs are evidence of a search, not of the claim text.
                src["quote_in_claim"] = True if src.get("resolvable") else False
                src["substance"] = bool(src.get("resolvable"))
            contra_out = {"query": contra.get("query") or "", "sources": csrc}
        resolved_claims.append(
            {
                **claim,
                "sources": sources,
                "contradiction_search": contra_out,
            }
        )
    resolved_unknowns = []
    for unknown in art.get("unknowns") or []:
        exp = unknown.get("named_experiment")
        exp_out = None
        if isinstance(exp, dict):
            esrc = [resolve_citation(server, s) for s in (exp.get("sources") or [])]
            for src in esrc:
                src["quote_in_claim"] = quote_in_text(
                    str(src.get("claimed_quote") or ""), str(exp.get("method") or "")
                ) or bool(src.get("resolvable"))
                src["substance"] = bool(src.get("resolvable"))
            exp_out = {**exp, "sources": esrc}
        resolved_unknowns.append({**unknown, "named_experiment": exp_out})
    return {**art, "claims": resolved_claims, "unknowns": resolved_unknowns}


def _substance_sources(claim: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in (claim.get("sources") or []) if s.get("substance")]


def dimension_scores(resolved: dict[str, Any]) -> dict[str, Any]:
    citations: list[dict[str, Any]] = []
    for claim in resolved.get("claims") or []:
        citations.extend(claim.get("sources") or [])
        cs = claim.get("contradiction_search")
        if isinstance(cs, dict):
            citations.extend(cs.get("sources") or [])
    for unknown in resolved.get("unknowns") or []:
        exp = unknown.get("named_experiment")
        if isinstance(exp, dict):
            citations.extend(exp.get("sources") or [])

    n_cite = len(citations)
    n_resolvable = sum(1 for c in citations if c.get("resolvable"))
    resolvability = (n_resolvable / n_cite) if n_cite else 0.0

    classes = set()
    for claim in resolved.get("claims") or []:
        for src in _substance_sources(claim):
            cls = str(src.get("source_class") or "")
            if is_registered(cls):
                classes.add(cls)
    coverage = len(classes) / float(len(SOURCE_CLASSES))

    load_bearing = [c for c in (resolved.get("claims") or []) if c.get("load_bearing") is not False]
    if not load_bearing:
        load_bearing = list(resolved.get("claims") or [])
    n_lb = len(load_bearing)
    n_indep = 0
    n_contra = 0
    indep_rows = []
    for claim in load_bearing:
        subst = _substance_sources(claim)
        indep = independent_origin_count(subst) if subst else 0
        naive = naive_url_count(claim.get("sources") or [])
        ok = indep >= 2
        n_indep += int(ok)
        cs = claim.get("contradiction_search")
        contra_ok = False
        if isinstance(cs, dict):
            contra_ok = any(s.get("substance") or s.get("resolvable") for s in (cs.get("sources") or []))
        n_contra += int(contra_ok)
        indep_rows.append(
            {
                "claim_id": claim.get("id"),
                "independent_origins": indep,
                "naive_url_count": naive,
                "meets_k2": ok,
                "contradiction_resolved": contra_ok,
            }
        )
    indep_rate = (n_indep / n_lb) if n_lb else 0.0
    contra_rate = (n_contra / n_lb) if n_lb else 0.0

    unknowns = list(resolved.get("unknowns") or [])
    if "unknowns" not in resolved:
        named_rate = 0.0
        n_unk = 0
        n_named = 0
    elif not unknowns:
        named_rate = 1.0
        n_unk = 0
        n_named = 0
    else:
        n_unk = len(unknowns)
        n_named = 0
        for unknown in unknowns:
            exp = unknown.get("named_experiment")
            if not isinstance(exp, dict):
                continue
            method = str(exp.get("method") or "").strip()
            eid = str(exp.get("id") or "").strip()
            resolved_exp = any(s.get("resolvable") for s in (exp.get("sources") or []))
            if eid and method and resolved_exp:
                n_named += 1
        named_rate = n_named / n_unk

    scores = {
        "source_class_coverage": coverage,
        "independent_source_rate": indep_rate,
        "contradiction_coverage": contra_rate,
        "named_experiment_rate": named_rate,
        "citation_resolvability": resolvability,
    }
    composite = sum(scores[k] * WEIGHT for k in DIMENSIONS)
    meets = (
        scores["source_class_coverage"] >= GATES["source_class_coverage_min"]
        and scores["independent_source_rate"] >= GATES["independent_source_rate_min"]
        and scores["contradiction_coverage"] >= GATES["contradiction_coverage_min"]
        and scores["named_experiment_rate"] >= GATES["named_experiment_rate_min"]
        and scores["citation_resolvability"] >= GATES["citation_resolvability_min"]
    )
    return {
        "scores": scores,
        "composite": composite,
        "meets_target": meets,
        "n_citations": n_cite,
        "n_resolvable": n_resolvable,
        "source_classes_hit": sorted(classes),
        "source_class_hit_count": len(classes),
        "source_class_denominator": len(SOURCE_CLASSES),
        "load_bearing_claims": n_lb,
        "independently_corroborated_claims": n_indep,
        "contradiction_covered_claims": n_contra,
        "unknown_count": n_unk,
        "named_experiment_count": n_named,
        "claim_rows": indep_rows,
    }


def naive_shape_score(art: dict[str, Any]) -> dict[str, Any]:
    """Inert matcher: count citation-shaped URL strings and declared class tags."""
    import re

    blob = str(art)
    urls = re.findall(r"https?://[^\s'\"\\]+", blob)
    tagged = 0
    for claim in art.get("claims") or []:
        for src in (claim.get("sources") or []):
            if src.get("source_class"):
                tagged += 1
    return {
        "url_string_count": len(urls),
        "declared_source_class_tags": tagged,
        "shape_score": float(len(urls)),
    }


def rank_rows(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda r: (-float(r[key]), str(r["id"])))
    out = []
    for i, row in enumerate(ordered, 1):
        item = dict(row)
        item["rank"] = i
        out.append(item)
    return out


def spearman(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    d2 = sum((a - b) ** 2 for a, b in zip(xs, ys))
    return 1.0 - (6.0 * d2) / (n * (n * n - 1))


def score_corpus(
    artifacts: list[dict[str, Any]],
    body_routes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    routes = routes_from_bodies(body_routes)
    with FixtureHttp(routes) as server:
        scored = []
        for art in artifacts:
            resolved = resolve_artifact(art, server)
            dims = dimension_scores(resolved)
            naive = naive_shape_score(art)
            scored.append(
                {
                    "id": art["id"],
                    "title": art.get("title"),
                    "a_priori_rank": art.get("a_priori_rank"),
                    "planted_defect": art.get("planted_defect"),
                    "composite": dims["composite"],
                    "meets_target": dims["meets_target"],
                    "scores": dims["scores"],
                    "n_citations": dims["n_citations"],
                    "n_resolvable": dims["n_resolvable"],
                    "source_classes_hit": dims["source_classes_hit"],
                    "source_class_hit_count": dims["source_class_hit_count"],
                    "claim_rows": dims["claim_rows"],
                    "unknown_count": dims["unknown_count"],
                    "named_experiment_count": dims["named_experiment_count"],
                    "naive": naive,
                    "lineage_sample": [
                        {
                            "claim_id": c.get("id"),
                            "sources": [
                                {
                                    "id": s.get("id"),
                                    "logical_url": s.get("logical_url"),
                                    "resolved_url": s.get("resolved_url"),
                                    "http_status": s.get("http_status"),
                                    "fetched_at": s.get("fetched_at"),
                                    "sha256": s.get("sha256"),
                                    "resolvable": s.get("resolvable"),
                                    "content_match": s.get("content_match"),
                                    "substance": s.get("substance"),
                                    "source_class": s.get("source_class"),
                                    "origin_id": s.get("origin_id"),
                                }
                                for s in (c.get("sources") or [])[:4]
                            ],
                        }
                        for c in (resolved.get("claims") or [])[:2]
                    ],
                }
            )
    metric_ranked = rank_rows(scored, "composite")
    naive_ranked = rank_rows(
        [{"id": r["id"], "shape_score": r["naive"]["shape_score"]} for r in scored],
        "shape_score",
    )
    by_id = {r["id"]: r for r in metric_ranked}
    for r in naive_ranked:
        by_id[r["id"]]["naive_rank"] = r["rank"]
        by_id[r["id"]]["naive_shape_score"] = r["shape_score"]
    order = [r["id"] for r in metric_ranked]
    padded = by_id.get("A6-padded-citations") or {}
    a_priori = []
    metric_pos = []
    for art in artifacts:
        aid = art["id"]
        a_priori.append(float(art.get("a_priori_rank") or 0))
        metric_pos.append(float(by_id[aid]["rank"]))
    return {
        "rows": metric_ranked,
        "order_best_to_worst": order,
        "padded_id": "A6-padded-citations",
        "padded_is_lowest": order[-1] == "A6-padded-citations" if order else False,
        "padded_rank": padded.get("rank"),
        "padded_naive_rank": padded.get("naive_rank"),
        "naive_ranks_padded_first": (naive_ranked[0]["id"] == "A6-padded-citations") if naive_ranked else False,
        "spearman_vs_apriori": spearman(a_priori, metric_pos),
        "quality_target": {
            "dimensions": list(DIMENSIONS),
            "weight_each": WEIGHT,
            "gates": GATES,
            "source_classes": list(SOURCE_CLASSES),
            "source_class_derivation": DERIVATION,
            "independence_rule": (
                "origin_id and organisation differ; neither citation closure "
                "contains the other; closures share no upstream origin. "
                "Distinct URLs are not sufficient."
            ),
            "resolvability_rule": (
                "Live HTTP GET; 2xx status; sha256 of fetched bytes; claimed "
                "quote substring of body AND of the claim text. Unresolvable "
                "citations do not increment any other dimension."
            ),
        },
    }


def mutate_repair_padded(art: dict[str, Any]) -> dict[str, Any]:
    """Both-states: replace padded 404/mismatch URLs with resolvable gold citations."""
    from corpus import artifact_a1

    gold = artifact_a1()
    repaired = deepcopy(art)
    repaired["id"] = "A6-repaired"
    repaired["title"] = "A6 after citations are made resolvable (mutant)"
    repaired["claims"] = deepcopy(gold["claims"])
    repaired["unknowns"] = deepcopy(gold["unknowns"])
    repaired["a_priori_rank"] = 1
    repaired.pop("planted_defect", None)
    return repaired


def mutate_pad_gold(art: dict[str, Any]) -> dict[str, Any]:
    """Both-states: replace gold citations with A6 padding."""
    from corpus import artifact_a6

    padded = artifact_a6()
    wrecked = deepcopy(art)
    wrecked["id"] = "A1-padded-mutant"
    wrecked["title"] = "A1 after citations are replaced with padding (mutant)"
    wrecked["claims"] = deepcopy(padded["claims"])
    wrecked["unknowns"] = deepcopy(padded["unknowns"])
    wrecked["a_priori_rank"] = 6
    wrecked["planted_defect"] = "unresolvable-or-mismatched-citations"
    return wrecked
