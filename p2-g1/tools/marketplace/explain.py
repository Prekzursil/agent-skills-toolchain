#!/usr/bin/env python3
"""why: millipoint ranking + quality + named policy cell."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCALE = 1000
K1 = 1200
B = 750


def sat_milli(tf: int, dl: int, avgdl: int) -> int:
    if tf <= 0:
        return 0
    avgdl = max(avgdl, 1)
    length = (SCALE - B) + (B * dl) // avgdl
    numerator = tf * (K1 + SCALE) * SCALE * SCALE
    denominator = tf * SCALE * SCALE + K1 * length
    return numerator // denominator


def idf_milli(n_docs: int, df: int) -> int:
    return ((n_docs - df + 1) * SCALE) // max(df, 1)


def demo_corpus() -> list[dict[str, Any]]:
    return [
        {
            "id": "pkg.alpha",
            "name": "alpha-json-lint",
            "description": "json lint helper for workspaces",
            "tags": ["json", "lint"],
            "skills": ["json.lint", "json.help"],
            "conformance_pass_rate": 40,
            "freshness": 80,
            "download_count": 10,
            "signature": "valid",
            "trust": "HIGH",
            "advisory": "clean",
        },
        {
            "id": "pkg.beta",
            "name": "beta-search",
            "description": "general search",
            "tags": ["search"],
            "skills": ["search.run"],
            "conformance_pass_rate": 70,
            "freshness": 50,
            "download_count": 5,
            "signature": "valid",
            "trust": "MED",
            "advisory": "low",
        },
        {
            "id": "pkg.delta",
            "name": "delta-unsigned",
            "description": "unsigned payload",
            "tags": ["misc"],
            "skills": [],
            "conformance_pass_rate": 10,
            "freshness": 10,
            "download_count": 1,
            "signature": "invalid",
            "trust": "LOW",
            "advisory": "critical",
        },
    ]


def _bag(pkg: dict[str, Any]) -> list[str]:
    parts = [
        str(pkg.get("name") or ""),
        str(pkg.get("description") or ""),
        *list(pkg.get("tags") or []),
        *list(pkg.get("skills") or []),
    ]
    tokens: list[str] = []
    for p in parts:
        tokens.extend(t.lower() for t in str(p).replace(".", " ").replace("-", " ").split() if t)
    return tokens


def _policy_cell(pkg: dict[str, Any]) -> dict[str, Any]:
    sig = str(pkg.get("signature") or "unknown")
    trust = str(pkg.get("trust") or "UNKNOWN")
    adv = str(pkg.get("advisory") or "unknown")
    cell = f"signature={sig}|trust={trust}|advisory={adv}"
    verdict = "ALLOW"
    if sig != "valid" or trust == "LOW" or adv == "critical":
        verdict = "DENY"
    msg = (
        f"policy cell {cell} verdict={verdict}"
        if verdict == "DENY"
        else f"allow via policy cell {cell}"
    )
    return {
        "cell_id": cell,
        "verdict": verdict,
        "specified_cell": True,
        "message": msg,
        "signature": sig,
        "trust": trust,
        "advisory": adv,
    }


def why(
    package_id: str,
    corpus: list[dict[str, Any]] | None = None,
    query: str = "",
    subject: str = "search",
) -> dict[str, Any]:
    corpus = list(corpus or demo_corpus())
    pkg = next(p for p in corpus if p["id"] == package_id)
    terms = [t.lower() for t in query.split() if t]
    docs = [_bag(p) for p in corpus]
    n_docs = max(len(docs), 1)
    avgdl = max(sum(len(d) for d in docs) // n_docs, 1)
    bag = _bag(pkg)
    dl = max(len(bag), 1)
    ranking_components = []
    rank_sum = 0
    for term in terms or ["_none"]:
        tf = bag.count(term) * SCALE
        df = sum(1 for d in docs if term in d) or (1 if term == "_none" else 0)
        if term == "_none":
            tf, df = 0, 1
        sat = sat_milli(tf, dl, avgdl)
        idf = idf_milli(n_docs, max(df, 1))
        value = (idf * sat) // SCALE
        rank_sum += value
        ranking_components.append(
            {
                "id": f"term:{term}",
                "term": term,
                "tf_weighted": tf,
                "dl": dl,
                "avgdl": avgdl,
                "N": n_docs,
                "df": max(df, 1),
                "sat_milli": sat,
                "idf_milli": idf,
                "value": value,
            }
        )
    quality_parts = [
        ("conformance_pass_rate", 400, int(pkg.get("conformance_pass_rate") or 0)),
        ("freshness", 300, int(pkg.get("freshness") or 0)),
        ("download_count", 300, int(pkg.get("download_count") or 0)),
    ]
    q_components = []
    q_sum = 0
    for cid, weight, measurement in quality_parts:
        meas = measurement * SCALE // 100 if cid != "download_count" else measurement * 20
        if cid == "download_count":
            meas = min(measurement * 20, SCALE)
        value = (weight * meas) // SCALE
        q_sum += value
        q_components.append(
            {
                "id": cid,
                "weight": weight,
                "measurement": meas,
                "value": value,
            }
        )
    policy = _policy_cell(pkg)
    human = [
        f"package {package_id}",
        f"ranking_milli={rank_sum}",
        f"quality_milli={q_sum}",
        policy["message"],
        f"policy cell {policy['cell_id']}",
    ]
    return {
        "package_id": package_id,
        "subject": subject,
        "query": query,
        "ranking": {
            "score_milli": rank_sum,
            "sum_components": rank_sum,
            "components": ranking_components,
        },
        "quality": {
            "score_milli": q_sum,
            "sum_components": q_sum,
            "components": q_components,
        },
        "policy": policy,
        "human_lines": human,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    why_p = sub.add_parser("why")
    why_p.add_argument("subject")
    why_p.add_argument("--package", required=True)
    why_p.add_argument("--query", default="")
    args = parser.parse_args(argv)
    if args.cmd != "why":
        print(json.dumps({"error": "usage: why <subject> --package ID"}))
        return 2
    report = why(package_id=args.package, query=args.query, subject=args.subject)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
