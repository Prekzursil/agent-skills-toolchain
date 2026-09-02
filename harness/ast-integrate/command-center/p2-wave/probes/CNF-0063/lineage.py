#!/usr/bin/env python3
"""Origin tracing for CNF-0063.

Independence is not distinct-URL counting. Two sources corroborate a claim
only when (1) origin_id differs, (2) organisation differs, (3) neither
source's citation closure contains the other origin, and (4) the citation
closures share no upstream origin. A second URL that reprints or cites the
first is single-sourced.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any
from urllib.parse import urlparse


INDEPENDENT = "INDEPENDENTLY-CORROBORATED"
SINGLE = "SINGLE-SOURCED"
LABEL_INDEP = "INDEPENDENT-SECOND-SOURCE"
LABEL_SINGLE = "SINGLE-SOURCED"


def canon(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def origin_id(src: dict[str, Any]) -> str:
    explicit = canon(str(src.get("origin_id") or ""))
    if explicit:
        return explicit
    org = canon(str(src.get("organisation") or ""))
    if org:
        return org
    url = str(src.get("url") or "")
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host:
        return host
    raise ValueError(f"source {src.get('id')!r} has no origin_id")


def cites_of(src: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in src.get("cites") or []:
        c = canon(str(item))
        if c:
            out.append(c)
    return out


def citation_closure(src: dict[str, Any], by_origin: dict[str, dict[str, Any]] | None = None) -> set[str]:
    """Origins this source depends on, including its own origin, transitively."""
    by_origin = by_origin or {}
    own = origin_id(src)
    seen: set[str] = {own}
    stack = list(cites_of(src))
    while stack:
        nid = stack.pop()
        if nid in seen:
            continue
        seen.add(nid)
        other = by_origin.get(nid)
        if other is not None:
            stack.extend(cites_of(other))
    return seen


def index_by_origin(sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    for src in sources:
        idx[origin_id(src)] = src
    return idx


def pair_independence(
    a: dict[str, Any],
    b: dict[str, Any],
    by_origin: dict[str, dict[str, Any]] | None = None,
) -> tuple[bool, str]:
    oa, ob = origin_id(a), origin_id(b)
    if oa == ob:
        return False, "same-origin"
    org_a = canon(str(a.get("organisation") or ""))
    org_b = canon(str(b.get("organisation") or ""))
    if org_a and org_b and org_a == org_b:
        return False, "same-organisation"
    by_origin = by_origin or {}
    ca = citation_closure(a, by_origin)
    cb = citation_closure(b, by_origin)
    if oa in (cb - {ob}):
        return False, "second-cites-first"
    if ob in (ca - {oa}):
        return False, "first-cites-second"
    up_a = ca - {oa}
    up_b = cb - {ob}
    shared = sorted(up_a & up_b)
    if shared:
        return False, "shared-upstream:" + ",".join(shared)
    return True, "independent"


def group_by_origin(sources: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for src in sources:
        groups.setdefault(origin_id(src), []).append(src)
    return groups


def naive_url_count_independent(sources: list[dict[str, Any]]) -> bool:
    """The inert matcher: two distinct URLs count as corroborated."""
    urls = {str(s.get("url") or "").strip() for s in sources if str(s.get("url") or "").strip()}
    return len(urls) >= 2


def classify_claim(claim: dict[str, Any]) -> dict[str, Any]:
    sources = list(claim.get("sources") or [])
    if not sources:
        raise ValueError(f"claim {claim.get('id')!r} has no sources")
    by_origin = index_by_origin(sources)
    groups = group_by_origin(sources)
    republication_groups = [
        {"origin_id": oid, "url_count": len(members), "urls": [m.get("url") for m in members]}
        for oid, members in sorted(groups.items())
        if len(members) > 1
    ]
    reps = [members[0] for members in groups.values()]
    independent_pairs: list[dict[str, Any]] = []
    pair_failures: list[dict[str, Any]] = []
    for a, b in combinations(reps, 2):
        ok, reason = pair_independence(a, b, by_origin)
        row = {
            "a": origin_id(a),
            "b": origin_id(b),
            "independent": ok,
            "reason": reason,
            "a_publisher": a.get("publisher"),
            "b_publisher": b.get("publisher"),
            "a_organisation": a.get("organisation"),
            "b_organisation": b.get("organisation"),
            "a_closure": sorted(citation_closure(a, by_origin)),
            "b_closure": sorted(citation_closure(b, by_origin)),
        }
        if ok:
            independent_pairs.append(row)
        else:
            pair_failures.append(row)

    if independent_pairs:
        verdict = INDEPENDENT
        label = LABEL_INDEP
        reason = "genuinely-independent-second-source"
        pair = independent_pairs[0]
        second_source = {
            "origin_id": pair["b"],
            "publisher": pair["b_publisher"],
            "organisation": pair["b_organisation"],
            "url": next(s["url"] for s in reps if origin_id(s) == pair["b"]),
        }
        first_source = {
            "origin_id": pair["a"],
            "publisher": pair["a_publisher"],
            "organisation": pair["a_organisation"],
            "url": next(s["url"] for s in reps if origin_id(s) == pair["a"]),
        }
    else:
        verdict = SINGLE
        label = LABEL_SINGLE
        if republication_groups and len(groups) == 1:
            reason = "republication-counted-twice"
        elif any(p["reason"] in {"second-cites-first", "first-cites-second"} for p in pair_failures):
            reason = "circular-citation"
        elif any(str(p["reason"]).startswith("shared-upstream") for p in pair_failures):
            reason = "shared-upstream-origin"
        elif len(sources) == 1:
            reason = "single-sourced-claim"
        else:
            reason = "not-independent"
        first_source = {
            "origin_id": origin_id(sources[0]),
            "publisher": sources[0].get("publisher"),
            "organisation": sources[0].get("organisation"),
            "url": sources[0].get("url"),
        }
        second_source = None
        if len(sources) > 1:
            second_source = {
                "origin_id": origin_id(sources[1]),
                "publisher": sources[1].get("publisher"),
                "organisation": sources[1].get("organisation"),
                "url": sources[1].get("url"),
                "not_independent_because": pair_failures[0]["reason"] if pair_failures else reason,
            }

    lineage_trace = {
        "method": "citation-closure-by-origin_id",
        "origins": sorted(groups),
        "origin_count": len(groups),
        "url_count": len({str(s.get("url") or "") for s in sources}),
        "republication_groups": republication_groups,
        "independent_pairs": independent_pairs,
        "pair_failures": pair_failures,
        "naive_url_count_would_call_independent": naive_url_count_independent(sources),
        "first_source": first_source,
        "second_source": second_source,
        "classification_reason": reason,
    }
    return {
        "id": claim["id"],
        "claim": claim["claim"],
        "planted": bool(claim.get("planted")),
        "kind": claim.get("kind") or "sampled",
        "sources": sources,
        "verdict": verdict,
        "label": label,
        "lineage_trace": lineage_trace,
        "failure_class": None if verdict == INDEPENDENT else reason,
    }


def classify_sample(claims: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [classify_claim(c) for c in claims]
    for row in rows:
        if row["verdict"] == INDEPENDENT and row["label"] != LABEL_INDEP:
            raise AssertionError(f"{row['id']} independent without second-source label")
        if row["verdict"] == SINGLE and row["label"] != LABEL_SINGLE:
            raise AssertionError(f"{row['id']} single-sourced without explicit label")
        if row["verdict"] not in {INDEPENDENT, SINGLE}:
            raise AssertionError(f"{row['id']} missing required label class")
    return {
        "claims": rows,
        "single_sourced_count": sum(1 for r in rows if r["verdict"] == SINGLE),
        "independently_corroborated_count": sum(1 for r in rows if r["verdict"] == INDEPENDENT),
        "republication_counted_twice_count": sum(
            1
            for r in rows
            if r["lineage_trace"]["republication_groups"]
            or r["failure_class"] == "republication-counted-twice"
        ),
        "circular_citation_count": sum(1 for r in rows if r["failure_class"] == "circular-citation"),
    }
