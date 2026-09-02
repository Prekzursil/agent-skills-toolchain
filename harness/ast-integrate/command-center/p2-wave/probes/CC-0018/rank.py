#!/usr/bin/env python3
"""CC-0018 ranking: independent evidence, never agent repetition.

Independence is source-set cardinality after lineage collapse (the catalog
retry pivot). Agent identity, echo counts, and raw lineage-row counts are
stripped before scoring and are not read by the scorer.
"""
from __future__ import annotations

from posixpath import normpath
from typing import Any, Iterable, Mapping

VERIFICATION = {
    "CONFIRMED": 4,
    "PARTIAL": 2,
    "UNVERIFIED": 1,
    "REFUTED": 0,
}
SEVERITY = {"critical": 4, "high": 3, "medium": 2, "low": 1}
IMPACT = {"critical": 4, "high": 3, "medium": 2, "low": 1}
CONFIDENCE = {
    "almost_certain": 5,
    "probable": 4,
    "even_chance": 3,
    "improbable": 2,
    "remote": 1,
}

CLAIM_FIELDS = (
    "claim_id",
    "canonical_mechanism",
    "duplicate_of",
    "duplicate_of",
    "support",
    "contradiction",
    "source_lineage",
    "verification_status",
    "severity",
    "implementation_impact",
    "confidence",
    "settling_probe",
)
LINEAGE_FIELDS = (
    "source_document",
    "path",
    "uri",
    "url",
    "source_sha256",
    "sha256",
    "domain",
)


def normalize_document(raw: str) -> str:
    s = str(raw).strip()
    if s.startswith("file://"):
        s = s[7:]
        if s.startswith("localhost/"):
            s = s[len("localhost/") :]
        if s.startswith("/") and not s.startswith("//"):
            # file:///docs/a.md -> /docs/a.md; keep as posix path
            pass
    s = s.split("#", 1)[0].split("?", 1)[0]
    s = s.replace("\\", "/")
    s = normpath(s)
    if s.startswith("./"):
        s = s[2:]
    while s.startswith("/./"):
        s = s[3:]
    if s.startswith("/") and len(s) > 1 and not s.startswith("//"):
        # Prefer repo-relative identity when the path is a synthetic fixture.
        pass
    if s.endswith("/") and s != "/":
        s = s[:-1]
    return s


def source_identity(entry: Mapping[str, Any]) -> str | None:
    sha = entry.get("source_sha256") or entry.get("sha256")
    if isinstance(sha, str) and sha.strip():
        return "sha256:" + sha.strip().lower()
    raw = (
        entry.get("source_document")
        or entry.get("path")
        or entry.get("uri")
        or entry.get("url")
        or ""
    )
    if not str(raw).strip():
        return None
    return "path:" + normalize_document(str(raw))


def ranking_view(claim: Mapping[str, Any]) -> dict[str, Any]:
    """Copy only fields the ranker is allowed to see."""
    view: dict[str, Any] = {}
    for key in CLAIM_FIELDS:
        if key not in claim:
            continue
        if key == "source_lineage":
            rows = []
            for entry in claim.get("source_lineage") or []:
                if not isinstance(entry, Mapping):
                    continue
                slim = {k: entry[k] for k in LINEAGE_FIELDS if k in entry}
                if slim:
                    rows.append(slim)
            view["source_lineage"] = rows
        else:
            view[key] = claim[key]
    return view


def source_set(claim: Mapping[str, Any]) -> frozenset[str]:
    found: set[str] = set()
    for entry in claim.get("source_lineage") or []:
        if not isinstance(entry, Mapping):
            continue
        ident = source_identity(entry)
        if ident:
            found.add(ident)
    return frozenset(found)


def domain_set(claim: Mapping[str, Any]) -> frozenset[str]:
    by_source: dict[str, str] = {}
    for entry in claim.get("source_lineage") or []:
        if not isinstance(entry, Mapping):
            continue
        ident = source_identity(entry)
        if not ident:
            continue
        domain = entry.get("domain")
        if isinstance(domain, str) and domain.strip():
            by_source.setdefault(ident, domain.strip())
    return frozenset(by_source.values())


def independent_signal_count(claims: Iterable[Mapping[str, Any]]) -> int:
    union: set[str] = set()
    for claim in claims:
        union |= set(source_set(ranking_view(claim)))
    return len(union)


def _band(table: Mapping[str, int], value: Any) -> int:
    if not isinstance(value, str):
        return 0
    return table.get(value.strip(), 0)


def score_components(claim: Mapping[str, Any]) -> dict[str, int]:
    view = ranking_view(claim)
    sources = source_set(view)
    domains = domain_set(view)
    return {
        "independent_evidence": len(sources),
        "cross_domain": len(domains),
        "verification": _band(VERIFICATION, view.get("verification_status")),
        "severity": _band(SEVERITY, view.get("severity")),
        "decision_impact": _band(IMPACT, view.get("implementation_impact")),
        "confidence": _band(CONFIDENCE, view.get("confidence")),
    }


def sort_key(claim: Mapping[str, Any]) -> tuple[int, ...]:
    c = score_components(claim)
    return (
        c["independent_evidence"],
        c["cross_domain"],
        c["verification"],
        c["severity"],
        c["decision_impact"],
        c["confidence"],
    )


def mechanism_bucket(claim: Mapping[str, Any]) -> str:
    dup = claim.get("duplicate_of") or claim.get("duplicate_of")
    if isinstance(dup, str) and dup.strip():
        return dup.strip()
    mech = claim.get("canonical_mechanism")
    if isinstance(mech, str) and mech.strip():
        return mech.strip()
    cid = claim.get("claim_id")
    return str(cid) if cid else ""


def merge_claims(claims: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[Mapping[str, Any]]] = {}
    for claim in claims:
        buckets.setdefault(mechanism_bucket(claim), []).append(claim)
    merged: list[dict[str, Any]] = []
    for bucket, group in buckets.items():
        head = ranking_view(group[0])
        lineage: list[dict[str, Any]] = []
        seen: set[str] = set()
        support: list[str] = []
        contradiction: list[str] = []
        ids: list[str] = []
        for item in group:
            cid = item.get("claim_id")
            if isinstance(cid, str) and cid:
                ids.append(cid)
            view = ranking_view(item)
            for edge in view.get("support") or []:
                if edge not in support:
                    support.append(edge)
            for edge in view.get("contradiction") or []:
                if edge not in contradiction:
                    contradiction.append(edge)
            for entry in view.get("source_lineage") or []:
                ident = source_identity(entry) or repr(sorted(entry.items()))
                if ident in seen:
                    continue
                seen.add(ident)
                lineage.append(dict(entry))
        best = max(group, key=sort_key)
        best_view = ranking_view(best)
        merged.append(
            {
                "claim_id": best_view.get("claim_id") or bucket,
                "merged_from": ids,
                "canonical_mechanism": bucket,
                "duplicate_of": None,
                "support": support,
                "contradiction": contradiction,
                "source_lineage": lineage,
                "verification_status": best_view.get("verification_status"),
                "severity": best_view.get("severity"),
                "implementation_impact": best_view.get("implementation_impact"),
                "confidence": best_view.get("confidence"),
                "settling_probe": best_view.get("settling_probe"),
            }
        )
    return merged


def rank_claims(claims: Iterable[Mapping[str, Any]], *, merge: bool = True) -> list[dict[str, Any]]:
    pool = merge_claims(claims) if merge else [ranking_view(c) for c in claims]
    rows: list[dict[str, Any]] = []
    for claim in pool:
        comps = score_components(claim)
        rows.append(
            {
                "claim_id": claim.get("claim_id"),
                "canonical_mechanism": claim.get("canonical_mechanism"),
                "merged_from": claim.get("merged_from") or [claim.get("claim_id")],
                "source_set": sorted(source_set(claim)),
                "domain_set": sorted(domain_set(claim)),
                "components": comps,
                "sort_key": list(sort_key(claim)),
                "claim": claim,
            }
        )
    rows.sort(
        key=lambda r: (
            [-x for x in r["sort_key"]],
            str(r.get("claim_id") or ""),
        )
    )
    prev: list[int] | None = None
    rank = 0
    for i, row in enumerate(rows):
        key = row["sort_key"]
        if key != prev:
            rank = i + 1
            prev = key
        row["rank"] = rank
    return rows


# Names used by scenario.py / probes (stable aliases).
ranking_view = ranking_view
merge_claims = merge_claims
independent_signal_count = independent_signal_count
