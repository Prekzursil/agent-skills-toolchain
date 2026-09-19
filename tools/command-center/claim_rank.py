#!/usr/bin/env python3
"""CC-0018: rank claim records by independent evidence, not repetition.

Spec anchors:
  - WORK-UNIT-CATALOG.json#CC-0018
  - rules/common/single-signal-verification.md §5 (N agents sharing one stale
    input are one lens, not N signals)

Ranking uses:
  - independent source-document cardinality after lineage collapse
  - cross-domain / method diversity across collapsed sources
  - verification status, confidence band, and decision-impact severity

Ranking MUST NOT rise because the same claim was repeated by more agents, more
echo records, or more lineage rows that resolve to the same source document.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

REPO = Path(__file__).resolve().parents[2]

VERIFICATION_WEIGHT: dict[str, float] = {
    "CONFIRMED": 4.0,
    "PARTIAL": 2.0,
    "UNVERIFIED": 0.5,
    "NOT-CHECKED": 0.25,
    "REFUTED": 0.0,
}

CONFIDENCE_WEIGHT: dict[str | None, float] = {
    "almost-certain": 3.0,
    "likely": 2.0,
    "uncertain": 1.0,
    None: 0.5,
}

_IMPACT_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"\b(critical|blocker|p0|sev-?0)\b", re.I), 4.0),
    (re.compile(r"\b(high|severe|sev-?1|decision-blocking)\b", re.I), 3.0),
    (re.compile(r"\b(medium|moderate|sev-?2)\b", re.I), 2.0),
    (re.compile(r"\b(low|minor|sev-?3)\b", re.I), 1.0),
    (re.compile(r"\b(cosmetic|test-only|noise)\b", re.I), 0.25),
]


def _collapse_path(path: str) -> str:
    """Normalize path separators, ./ ../, and trailing slashes."""
    path = path.replace("\\", "/")
    path = path.split("#", 1)[0].split("?", 1)[0]
    path = re.sub(r"/+", "/", path)
    while path.startswith("./"):
        path = path[2:]
    bits: list[str] = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == ".." and bits and bits[-1] != "..":
            bits.pop()
            continue
        bits.append(part)
    path = "/".join(bits)
    if path.endswith("/"):
        path = path[:-1]
    return path


def normalize_source_document(anchor: str) -> str:
    """Collapse lineage anchors that name the same source document.

    Path aliases (./, ../, duplicate slashes), trailing slashes, URL fragments,
    query strings, opaque-URL trailing slashes (shared://doc vs shared://doc/),
    and file:// / file://localhost twins of a path-shaped anchor do not create
    new independent signals.
    """
    raw = (anchor or "").strip()
    if not raw:
        return ""

    lower = raw.lower()
    if "://" in lower or lower.startswith("file:"):
        parts = urlsplit(raw)
        scheme = parts.scheme.lower()
        netloc = parts.netloc.lower()
        path = re.sub(r"/+", "/", parts.path or "")
        # urlsplit("shared://one-doc/") keeps netloc=one-doc and path="/".
        # Treat bare "/" as empty so trailing-slash opaque URLs collapse.
        if path == "/":
            path = ""
        elif path.endswith("/"):
            path = path[:-1]

        # file:///docs/x.md and file://localhost/docs/x.md ≡ docs/x.md
        if scheme == "file" and netloc in ("", "localhost", "localhost."):
            return _collapse_path(path.lstrip("/") or path)

        # Drop fragment + query: same document, different view.
        return urlunsplit((scheme, netloc, path, "", ""))

    # Filesystem / repo-relative anchors.
    return _collapse_path(raw)


def normalize_method(method: str | None) -> str:
    if not method or not str(method).strip():
        return ""
    # Strip trivial whitespace / case so "File-Read" and "file-read" match.
    text = re.sub(r"\s+", " ", str(method).strip().lower())
    return text


def cluster_key(record: dict[str, Any]) -> str:
    """Group echo records that assert the same mechanism / claim text."""
    mech = record.get("canonical_mechanism")
    if isinstance(mech, str) and mech.strip():
        return re.sub(r"\s+", " ", mech.strip().lower())
    text = record.get("claim_text")
    if isinstance(text, str) and text.strip():
        return re.sub(r"\s+", " ", text.strip().lower())
    cid = record.get("claim_id")
    if isinstance(cid, str) and cid.strip():
        return cid.strip().lower()
    return f"anon:{hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()[:12]}"


def impact_weight(text: str) -> float:
    if not isinstance(text, str) or not text.strip():
        return 1.0
    for pattern, weight in _IMPACT_PATTERNS:
        if pattern.search(text):
            return weight
    return 1.0


def independent_signals(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Return collapsed independent source + method sets for a claim cluster.

    Lineage rows that normalize to the same source document count once.
    Methods are collected per collapsed source (not per echo record), so
    renaming probes / settling strings across N agents on one source cannot
    inflate method diversity. Repetition count is reported but is never an
    input to the score or rank tiebreak.
    """
    # source -> set of probe methods observed on that source
    methods_by_source: dict[str, set[str]] = {}
    settling_methods: set[str] = set()

    def _add(doc: str, method: str) -> None:
        if not doc:
            return
        bucket = methods_by_source.setdefault(doc, set())
        if method:
            bucket.add(method)

    for rec in records:
        lineage = rec.get("source_lineage") or []
        if isinstance(lineage, list):
            for entry in lineage:
                if not isinstance(entry, dict):
                    continue
                anchor = entry.get("anchor")
                doc = (
                    normalize_source_document(anchor) if isinstance(anchor, str) else ""
                )
                method = normalize_method(entry.get("probe"))
                if doc:
                    _add(doc, method)
        settling = normalize_method(rec.get("settling_probe"))
        if settling:
            # Settling probe is cluster-level intent, not per-echo diversity.
            settling_methods.add(settling)
        legacy = rec.get("legacy_fields") or {}
        if isinstance(legacy, dict):
            extra = legacy.get("independent_probes") or []
            if isinstance(extra, list):
                for probe in extra:
                    if not isinstance(probe, dict):
                        continue
                    anchor = probe.get("anchor")
                    doc = (
                        normalize_source_document(anchor)
                        if isinstance(anchor, str)
                        else ""
                    )
                    method = normalize_method(probe.get("method") or probe.get("probe"))
                    if doc:
                        _add(doc, method)

    sources = sorted(methods_by_source)
    # Method diversity is cross-source, not per-echo. Echo agents that rename
    # probes on the SAME collapsed source contribute at most one method token
    # for that source (sorted first label). Settling contributes at most one
    # cluster-level token.
    methods: set[str] = set()
    for doc in sources:
        src_methods = methods_by_source[doc]
        if src_methods:
            methods.add(sorted(src_methods)[0])
    if settling_methods:
        methods.add(sorted(settling_methods)[0])

    return {
        "independent_sources": sources,
        "independent_source_count": len(sources),
        "independent_methods": sorted(methods),
        "independent_method_count": len(methods),
        "repetition_count": len(records),
    }


def score_cluster(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Score a cluster of claim records that share a mechanism.

    Deliberately ignores ``len(records)`` / agent echo count. Score is a
    function of collapsed independent sources, method diversity, and the best
    quality fields in the cluster (verification, confidence, impact).
    """
    if not records:
        return {
            "score": 0.0,
            "independent_sources": [],
            "independent_source_count": 0,
            "independent_methods": [],
            "independent_method_count": 0,
            "repetition_count": 0,
            "best_verification": None,
            "best_confidence": None,
            "best_impact_weight": 0.0,
            "formula": "score = sources * (1 + 0.5*(methods-1)) * quality",
        }

    signals = independent_signals(records)
    n_sources = int(signals["independent_source_count"])
    n_methods = int(signals["independent_method_count"])

    best_ver_label = max(
        records,
        key=lambda r: VERIFICATION_WEIGHT.get(str(r.get("verification_status")), 0.0),
    ).get("verification_status")
    best_ver = VERIFICATION_WEIGHT.get(str(best_ver_label), 0.0)

    best_conf_label = max(
        records,
        key=lambda r: CONFIDENCE_WEIGHT.get(r.get("confidence"), 0.5),
    ).get("confidence")
    best_conf = CONFIDENCE_WEIGHT.get(best_conf_label, 0.5)

    best_impact = max(
        impact_weight(str(r.get("implementation_impact") or "")) for r in records
    )

    # Independence is source-set cardinality after lineage collapse.
    # Method-label proliferation on a SINGLE source must not raise independence
    # (adversarial control / retry_policy: prefer source-set cardinality over
    # weight tuning). Cross-domain bonus applies only when >=2 sources.
    independence = float(n_sources)
    if n_sources >= 2 and n_methods >= 2:
        independence *= 1.0 + 0.25 * (min(n_methods, n_sources) / n_sources)

    quality = (
        (1.0 + 0.25 * best_ver) * (1.0 + 0.15 * best_conf) * (1.0 + 0.2 * best_impact)
    )
    # Zero sources → zero independence (cannot invent signal from echo count).
    score = independence * quality

    return {
        "score": round(score, 6),
        "independent_sources": signals["independent_sources"],
        "independent_source_count": signals["independent_source_count"],
        "independent_methods": signals["independent_methods"],
        "independent_method_count": signals["independent_method_count"],
        "repetition_count": signals["repetition_count"],
        "best_verification": best_ver_label,
        "best_confidence": best_conf_label,
        "best_impact_weight": best_impact,
        "quality_multiplier": round(quality, 6),
        "independence": round(independence, 6),
        "formula": (
            "score = independent_source_count "
            "* (1 + 0.25*min(methods,sources)/sources if sources>=2 and methods>=2 else 1) "
            "* (1+0.25*ver) * (1+0.15*conf) * (1+0.2*impact); "
            "repetition_count and same-source method aliases are NOT factors"
        ),
    }


def rank_claims(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank claim clusters by independent-evidence score (descending).

    Returns one row per ``canonical_mechanism`` cluster. Echo / agent
    repetition widens ``member_claim_ids`` and ``repetition_count`` but cannot
    raise ``score`` without a new independent source or method.
    """
    clusters: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        clusters.setdefault(cluster_key(rec), []).append(rec)

    ranked: list[dict[str, Any]] = []
    for key, members in clusters.items():
        breakdown = score_cluster(members)
        ranked.append(
            {
                "cluster_key": key,
                "representative_claim_id": members[0].get("claim_id"),
                "member_claim_ids": [m.get("claim_id") for m in members],
                "member_count": len(members),
                **breakdown,
            }
        )

    # Tiebreak MUST NOT use independent_method_count: echo agents that invent
    # distinct probe labels on one shared source previously climbed rank via
    # method inflation while score stayed flat (CC-0018 adversarial FAIL).
    ranked.sort(
        key=lambda row: (
            -float(row["score"]),
            -int(row["independent_source_count"]),
            str(row["cluster_key"]),
        )
    )
    for i, row in enumerate(ranked, start=1):
        row["rank"] = i
    return ranked


def find_rank(
    ranked: list[dict[str, Any]],
    claim_id: str | None = None,
    *,
    cluster: str | None = None,
) -> dict[str, Any] | None:
    """Locate a ranked row by claim id membership or cluster key."""
    if cluster is not None:
        ck = re.sub(r"\s+", " ", cluster.strip().lower())
        for row in ranked:
            if row["cluster_key"] == ck:
                return row
    if claim_id is not None:
        for row in ranked:
            if (
                claim_id in (row.get("member_claim_ids") or [])
                or row.get("representative_claim_id") == claim_id
            ):
                return row
    return None


def adversarial_repetition_run(
    base_claim: dict[str, Any],
    *,
    n_values: list[int],
    background: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute the catalog adversarial control: echo one claim across N agents.

    Prints / returns before-and-after ranks. Rank/score must be flat across N
    when all echoes share one source document.
    """
    background = list(background or [])
    mech = str(base_claim.get("canonical_mechanism") or "adversarial-claim")
    source = (base_claim.get("source_lineage") or [{}])[0].get(
        "anchor", "shared://stale"
    )
    results: list[dict[str, Any]] = []

    for n in n_values:
        echoes: list[dict[str, Any]] = []
        for i in range(n):
            echo = json.loads(json.dumps(base_claim))
            echo["claim_id"] = f"{base_claim.get('claim_id', 'ADV')}-agent-{i + 1}"
            echo["canonical_mechanism"] = mech
            echo["source_lineage"] = [
                {
                    "anchor": source,
                    # Distinct agent labels on purpose: gaming via renamed probes
                    # on one shared source must still fail to raise rank.
                    "probe": f"agent-{i + 1}-read",
                    "note": "synthetic echo sharing one source",
                }
            ]
            legacy = dict(echo.get("legacy_fields") or {})
            legacy["agent_id"] = f"synthetic-agent-{i + 1}"
            echo["legacy_fields"] = legacy
            echoes.append(echo)
        ranked = rank_claims(background + echoes)
        row = find_rank(ranked, cluster=mech)
        results.append(
            {
                "n_agents": n,
                "rank": None if row is None else row["rank"],
                "score": None if row is None else row["score"],
                "independent_source_count": None
                if row is None
                else row["independent_source_count"],
                "repetition_count": None if row is None else row["repetition_count"],
                "member_claim_ids": None if row is None else row["member_claim_ids"],
            }
        )

    scores = [r["score"] for r in results]
    ranks = [r["rank"] for r in results]
    flat = len(set(scores)) == 1 and len(set(ranks)) == 1
    return {
        "ok": flat,
        "property": "anti-repetition: rank/score must not rise with N shared-source echoes",
        "n_values": n_values,
        "before": results[0] if results else None,
        "after": results[-1] if results else None,
        "series": results,
        "score_rose": (scores[-1] or 0) > (scores[0] or 0) if scores else False,
        "rank_improved": ((ranks[-1] or 999) < (ranks[0] or 999) if ranks else False),
    }


def _cli_rank(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "claims" in data:
        records = data["claims"]
    elif isinstance(data, list):
        records = data
    else:
        print("input must be a claim list or {claims:[...]}", file=sys.stderr)
        return 2
    ranked = rank_claims(records)
    print(json.dumps({"ok": True, "count": len(ranked), "ranked": ranked}, indent=2))
    return 0


def _cli_adversarial() -> int:
    base = {
        "schema_version": 1,
        "schema_status": "PROVISIONAL",
        "superseded_by_unit": "ARC-0085",
        "claim_id": "ADV-BASE",
        "canonical_mechanism": "stale-premise-ground-truth",
        "duplicate_of": [],
        "supports": [],
        "contradicts": [],
        "source_lineage": [
            {"anchor": "docs://stale-premise.md", "probe": "agent-read"}
        ],
        "confidence": "likely",
        "verification_status": "UNVERIFIED",
        "implementation_impact": "medium — carried forward as ground truth",
        "settling_probe": "re-read docs://stale-premise.md",
    }
    # Fixed background so rank position is meaningful.
    background = [
        {
            "schema_version": 1,
            "schema_status": "PROVISIONAL",
            "superseded_by_unit": "ARC-0085",
            "claim_id": "BG-STRONG",
            "canonical_mechanism": "background-strong-independent",
            "duplicate_of": [],
            "supports": [],
            "contradicts": [],
            "source_lineage": [
                {"anchor": "probes://strong-a", "probe": "command"},
                {"anchor": "probes://strong-b", "probe": "file-read"},
            ],
            "confidence": "almost-certain",
            "verification_status": "CONFIRMED",
            "implementation_impact": "high — decision-blocking",
            "settling_probe": "pytest tools/command-center/tests/test_claim_rank.py -q",
        },
        {
            "schema_version": 1,
            "schema_status": "PROVISIONAL",
            "superseded_by_unit": "ARC-0085",
            "claim_id": "BG-WEAK",
            "canonical_mechanism": "background-weak-single-source",
            "duplicate_of": [],
            "supports": [],
            "contradicts": [],
            "source_lineage": [{"anchor": "notes://weak.txt", "probe": "skim"}],
            "confidence": "uncertain",
            "verification_status": "NOT-CHECKED",
            "implementation_impact": "low — cosmetic",
            "settling_probe": "manual skim notes://weak.txt",
        },
    ]
    report = adversarial_repetition_run(
        base, n_values=[1, 3, 10, 25], background=background
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return (
        0
        if report["ok"] and not report["score_rose"] and not report["rank_improved"]
        else 1
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_rank = sub.add_parser("rank", help="Rank claims from a JSON file")
    p_rank.add_argument("path", type=Path)
    sub.add_parser("adversarial", help="Run shared-source N-agent anti-repetition demo")
    sub.add_parser("meta", help="Print module contract metadata")
    args = parser.parse_args(argv)

    if args.cmd == "rank":
        return _cli_rank(args.path)
    if args.cmd == "adversarial":
        return _cli_adversarial()
    if args.cmd == "meta":
        print(
            json.dumps(
                {
                    "unit": "CC-0018",
                    "ranks_by": [
                        "independent_source_count_after_lineage_collapse",
                        "independent_method_diversity",
                        "verification_status",
                        "confidence",
                        "implementation_impact",
                    ],
                    "does_not_rank_by": [
                        "repetition_count",
                        "agent_echo_count",
                        "len(records)",
                    ],
                    "schema_input": "command-center/schema/claim-record.provisional.v1.schema.json",
                },
                indent=2,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
