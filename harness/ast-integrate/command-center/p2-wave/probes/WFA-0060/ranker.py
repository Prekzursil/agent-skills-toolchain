#!/usr/bin/env python3
"""Rank mechanisms by independent-evidence leverage, not by repetition.

Two artifacts that share one upstream source count once. Frequency (how many
artifacts repeated the same idea) is computed and published, but it is not an
input to leverage_score.
"""
from __future__ import annotations

from typing import Any

ECHO_ID = "mech.echo.planted-stale-brief"
FANIN_ID = "mech.fanin.blocking-barrier"
PARTIAL_ID = "mech.partial.shared-upstream-plus-one"
REPLAY_ID = "mech.replay.deterministic"
SINGLE_ID = "mech.single.strong-probe"

LEVERAGE_INPUTS = (
    "independent_evidence",
    "cross_domain_convergence",
    "severity",
    "decision_impact",
)
LEVERAGE_EXCLUDES = ("frequency", "agent_repeat_count", "artifact_count")


def leverage_score(
    independent_n: int,
    domain_n: int,
    severity: int,
    decision_impact: int,
) -> int:
    """Decision-impact leverage. Frequency is not a parameter and must stay out."""
    if min(independent_n, domain_n, severity, decision_impact) < 0:
        raise ValueError("leverage inputs must be non-negative")
    return int(independent_n) * int(domain_n) * int(severity) * int(decision_impact)


def naive_frequency_as_evidence_score(
    frequency: int,
    domain_n: int,
    severity: int,
    decision_impact: int,
) -> int:
    """Known-bad mutant: treat repetition as independent evidence.

    Used only as the both-states BAD arm. Never used for published leverage.
    """
    return int(frequency) * int(domain_n) * int(severity) * int(decision_impact)


def collapse_incidences(incidences: list[dict]) -> list[dict]:
    """Collapse artifacts that share an upstream source into one evidence unit."""
    buckets: dict[str, list[dict]] = {}
    for inc in incidences:
        up = str(inc["upstream_id"])
        buckets.setdefault(up, []).append(inc)
    collapsed: list[dict] = []
    for up in sorted(buckets):
        items = buckets[up]
        artifact_ids = sorted({str(i["artifact_id"]) for i in items})
        domains = sorted({str(i["domain"]) for i in items})
        collapsed.append(
            {
                "artifact_ids": artifact_ids,
                "counts_as_independent_evidence": 1,
                "domains": domains,
                "raw_artifact_count": len(artifact_ids),
                "upstream_id": up,
            }
        )
    return collapsed


def _tags(frequency: int, independent_n: int) -> list[str]:
    tags: list[str] = []
    if independent_n == 1:
        tags.append("SINGLE-SOURCE")
    if frequency >= 3 and independent_n == 1:
        tags.append("ECHO")
    return tags


def _echo_vs_signal(tags: list[str], independent_n: int) -> str:
    if "ECHO" in tags:
        return "ECHO"
    if independent_n == 1:
        return "SINGLE-SOURCE"
    return "SIGNAL"


def score_mechanism(mech: dict) -> dict[str, Any]:
    incidences = list(mech.get("incidences") or [])
    artifact_ids = sorted({str(i["artifact_id"]) for i in incidences})
    frequency = len(artifact_ids)
    collapsed = collapse_incidences(incidences)
    independent_n = len(collapsed)
    domains = sorted({d for c in collapsed for d in c["domains"]})
    domain_n = len(domains)
    severity = int(mech["severity"])
    decision_impact = int(mech["decision_impact"])
    lev = leverage_score(independent_n, domain_n, severity, decision_impact)
    naive = naive_frequency_as_evidence_score(
        frequency, domain_n, severity, decision_impact
    )
    tags = _tags(frequency, independent_n)
    evidence_sources = [
        {
            "artifact_id": str(i["artifact_id"]),
            "artifact_kind": str(i.get("artifact_kind") or ""),
            "domain": str(i["domain"]),
            "upstream_id": str(i["upstream_id"]),
        }
        for i in sorted(
            incidences,
            key=lambda x: (str(x["artifact_id"]), str(x["upstream_id"])),
        )
    ]
    return {
        "cross_domain_convergence": domain_n,
        "decision_impact": decision_impact,
        "definition": str(mech.get("definition") or ""),
        "domains": domains,
        "echo_vs_signal": _echo_vs_signal(tags, independent_n),
        "evidence_sources": evidence_sources,
        "frequency": frequency,
        "id": str(mech["mechanism_id"]),
        "independence_asserted": True,
        "independent_evidence": independent_n,
        "independent_sources": collapsed,
        "leverage_score": lev,
        "mechanism_id": str(mech["mechanism_id"]),
        "naive_frequency_as_evidence_score": naive,
        "severity": severity,
        "single_source": independent_n == 1,
        "tags": tags,
    }


def _rank_ids(rows: list[dict], score_key: str) -> dict[str, int]:
    ordered = sorted(
        rows,
        key=lambda r: (-int(r[score_key]), str(r["mechanism_id"])),
    )
    return {r["mechanism_id"]: i + 1 for i, r in enumerate(ordered)}


def rank_mechanisms(mechanisms: list[dict]) -> dict[str, Any]:
    rows = [score_mechanism(m) for m in mechanisms]
    lev_rank = _rank_ids(rows, "leverage_score")
    freq_rank = _rank_ids(rows, "frequency")
    naive_rank = _rank_ids(rows, "naive_frequency_as_evidence_score")
    for r in rows:
        mid = r["mechanism_id"]
        r["leverage_rank"] = lev_rank[mid]
        r["frequency_rank"] = freq_rank[mid]
        r["naive_frequency_as_evidence_rank"] = naive_rank[mid]
        sharp = int(r["frequency_rank"]) + 2 <= int(r["leverage_rank"])
        r["sharp_disagreement"] = sharp
        if sharp and "ECHO" not in r["tags"] and r["frequency"] > r["independent_evidence"]:
            r["tags"] = list(r["tags"]) + ["ECHO-CANDIDATE"]

    leverage_ranking = [
        {
            "leverage_rank": r["leverage_rank"],
            "leverage_score": r["leverage_score"],
            "mechanism_id": r["mechanism_id"],
            "tags": list(r["tags"]),
        }
        for r in sorted(rows, key=lambda x: x["leverage_rank"])
    ]
    frequency_ranking = [
        {
            "frequency": r["frequency"],
            "frequency_rank": r["frequency_rank"],
            "mechanism_id": r["mechanism_id"],
            "tags": list(r["tags"]),
        }
        for r in sorted(rows, key=lambda x: x["frequency_rank"])
    ]
    disagreements = [
        {
            "finding": r["echo_vs_signal"],
            "frequency_rank": r["frequency_rank"],
            "leverage_rank": r["leverage_rank"],
            "mechanism_id": r["mechanism_id"],
            "note": (
                "high frequency, low independent evidence: echo rather than signal"
                if r["echo_vs_signal"] == "ECHO"
                else "leverage and frequency ranks disagree"
            ),
        }
        for r in sorted(rows, key=lambda x: x["mechanism_id"])
        if r["sharp_disagreement"] or r["echo_vs_signal"] == "ECHO"
    ]
    by_id = {r["mechanism_id"]: r for r in rows}
    return {
        "by_id": by_id,
        "disagreements": disagreements,
        "frequency_ranking": frequency_ranking,
        "leverage_ranking": leverage_ranking,
        "records": sorted(rows, key=lambda r: r["leverage_rank"]),
    }
