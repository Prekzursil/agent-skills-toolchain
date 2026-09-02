#!/usr/bin/env python3
"""Measure injected-token growth at 10, 100, and 500 installed capabilities."""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.router.inject import (  # noqa: E402
    DEFAULT_CEILING,
    DEFAULT_K,
    count_payload_tokens,
    inject_topk,
    inject_unbounded_flood,
    payload_sha256,
)

INSTALLED_COUNTS = (10, 100, 500)
Z95 = 1.959963984540054

# Shared vocabulary so an ambiguous query matches the whole catalogue.
FILLER = (
    "This capability procedure harness documents a bounded operating method "
    "including inputs outputs refusal cases and a do-not-use-for clause so a "
    "naive session cannot dump the catalogue into turn context. Padding tokens "
    "keep per-skill payload cost realistic: alpha bravo charlie delta echo "
    "foxtrot golf hotel india juliet kilo lima mike november oscar papa."
)

PLANTED: list[dict[str, Any]] = [
    {
        "capability_id": "cap.git-commit",
        "name": "git commit helper",
        "triggers": ["git", "commit", "staged"],
        "description": (
            "Draft a git commit message for staged files. Use when the user "
            "asks to commit. Do-not-use-for: merging, rebasing, or force push. "
            + FILLER
        ),
    },
    {
        "capability_id": "cap.python-pytest",
        "name": "python pytest runner",
        "triggers": ["pytest", "python", "unittest"],
        "description": (
            "Run the python pytest suite and report failures. Use for unit "
            "tests. Do-not-use-for: production deploys. " + FILLER
        ),
    },
    {
        "capability_id": "cap.docker-compose",
        "name": "docker compose",
        "triggers": ["docker", "compose", "container"],
        "description": (
            "Manage docker compose services. Use for local containers. "
            "Do-not-use-for: kubernetes cluster changes. " + FILLER
        ),
    },
    {
        "capability_id": "cap.sql-migration",
        "name": "sql migration",
        "triggers": ["sql", "migration", "schema"],
        "description": (
            "Author a sql schema migration. Use for additive DDL. "
            "Do-not-use-for: dropping production tables. " + FILLER
        ),
    },
    {
        "capability_id": "cap.markdown-docs",
        "name": "markdown docs",
        "triggers": ["markdown", "docs", "readme"],
        "description": (
            "Edit markdown documentation and README files. Do-not-use-for: "
            "binary assets. " + FILLER
        ),
    },
    {
        "capability_id": "cap.kubernetes-probe",
        "name": "kubernetes probe",
        "triggers": ["kubernetes", "k8s", "probe"],
        "description": (
            "Configure kubernetes liveness and readiness probes. "
            "Do-not-use-for: deleting namespaces. " + FILLER
        ),
    },
]

QUERIES: list[dict[str, str]] = [
    {
        "id": "q-git",
        "text": "write a git commit message for the staged files",
        "expect_id": "cap.git-commit",
    },
    {
        "id": "q-pytest",
        "text": "run the python pytest suite and show failures",
        "expect_id": "cap.python-pytest",
    },
    {
        "id": "q-docker",
        "text": "start the docker compose container stack locally",
        "expect_id": "cap.docker-compose",
    },
    {
        "id": "q-sql",
        "text": "add a sql schema migration for the new column",
        "expect_id": "cap.sql-migration",
    },
    {
        "id": "q-docs",
        "text": "update the markdown docs README with the new flag",
        "expect_id": "cap.markdown-docs",
    },
    {
        "id": "q-k8s",
        "text": "set a kubernetes liveness probe on the k8s deployment",
        "expect_id": "cap.kubernetes-probe",
    },
    {
        "id": "q-ambiguous",
        "text": "capability procedure harness overflow budget",
        "expect_id": "",
    },
    {
        "id": "q-nomatch",
        "text": "qwxzzzy plugh fnord 918273xyz",
        "expect_id": "",
    },
]


def make_catalogue(n: int) -> list[dict[str, Any]]:
    """Deterministic catalogue of size n. Planted skills occupy the front."""
    if n < 1:
        raise ValueError("catalogue size must be positive")
    out: list[dict[str, Any]] = []
    planted = PLANTED[: min(len(PLANTED), n)]
    out.extend(dict(p) for p in planted)
    i = len(out)
    while i < n:
        out.append(
            {
                "capability_id": f"cap.distractor-{i:04d}",
                "name": f"distractor skill {i:04d}",
                "triggers": [f"distractor{i:04d}"],
                "description": (
                    f"Distractor {i:04d} is a unique unused procedure. "
                    f"Do-not-use-for: matching labelled routing queries. {FILLER}"
                ),
            }
        )
        i += 1
    return out


def moments(xs: list[int]) -> dict[str, Any]:
    """Bessel-corrected sample moments. n must be >= 2 for a variance band."""
    n = len(xs)
    if n < 1:
        raise ValueError("moments() needs at least one observation")
    mean = sum(xs) / float(n)
    if n < 2:
        var = 0.0
    else:
        var = sum((x - mean) ** 2 for x in xs) / float(n - 1)
    std = math.sqrt(var)
    se = std / math.sqrt(n) if n else 0.0
    return {
        "derived_from": "raw_runs",
        "n": n,
        "mean": mean,
        "sample_variance": var,
        "sample_std": std,
        "se": se,
        "ci95_low": mean - Z95 * se,
        "ci95_high": mean + Z95 * se,
        "min": min(xs),
        "max": max(xs),
        "sum": int(sum(xs)),
    }


def is_sublinear(tokens_by_n: dict[int, int]) -> dict[str, Any]:
    """Sublinear in installed count: T(n)/n strictly decreases and T(500)/T(10) << 50."""
    t10 = int(tokens_by_n[10])
    t100 = int(tokens_by_n[100])
    t500 = int(tokens_by_n[500])
    # Zero at every size is measured-nothing, not sublinear routing.
    if t10 <= 0:
        return {"pass": False, "reason": "t(10)=0 measured-nothing", "t10": t10, "t100": t100, "t500": t500}
    r10 = t10 / 10.0
    r100 = t100 / 100.0
    r500 = t500 / 500.0
    ratio_500_10 = t500 / float(t10)
    linear_500 = t10 * 50
    ok = (
        r100 < r10
        and r500 < r100
        and ratio_500_10 < 5.0
        and t500 < 0.2 * linear_500
    )
    return {
        "pass": ok,
        "t10": t10,
        "t100": t100,
        "t500": t500,
        "tokens_per_installed": {"10": r10, "100": r100, "500": r500},
        "t500_over_t10": ratio_500_10,
        "linear_expectation_t500": linear_500,
    }


def is_linear_growth(tokens_by_n: dict[int, int], *, min_ratio: float = 20.0) -> dict[str, Any]:
    """Flood path: T(500)/T(10) near 50. min_ratio=20 still far from top-k's ~1."""
    t10 = int(tokens_by_n[10])
    t500 = int(tokens_by_n[500])
    if t10 <= 0:
        return {"pass": False, "reason": "t(10)=0", "t10": t10, "t500": t500, "ratio": None}
    ratio = t500 / float(t10)
    return {
        "pass": ratio >= min_ratio,
        "t10": t10,
        "t100": int(tokens_by_n[100]),
        "t500": t500,
        "ratio": ratio,
        "min_ratio": min_ratio,
    }


def _run_row(n: int, query: dict[str, str], result: dict[str, Any]) -> dict[str, Any]:
    payload = str(result.get("payload") or "")
    tokens = int(result["injected_tokens"])
    recount = count_payload_tokens(payload)
    return {
        "installed_count": n,
        "query_id": query["id"],
        "query": query["text"],
        "expect_id": query.get("expect_id") or "",
        "path": result["path"],
        "injected_tokens": tokens,
        "recount_tokens": recount,
        "recount_ok": recount == tokens,
        "payload_sha256": result["payload_sha256"],
        "payload_sha256_recomputed": payload_sha256(payload),
        "chars_div_4_estimate": int(result["chars_div_4_estimate"]),
        "admitted_ids": list(result.get("admitted_ids") or []),
        "selected_count": int(result.get("selected_count") or len(result.get("admitted_ids") or [])),
        "k": result.get("k"),
        "payload": payload,
        "used_estimate_as_primary": tokens == int(result["chars_div_4_estimate"]) and tokens > 0 and tokens != recount,
    }


def measure_all(
    *,
    k: int = DEFAULT_K,
    ceiling: int = DEFAULT_CEILING,
) -> dict[str, Any]:
    catalogues = {n: make_catalogue(n) for n in INSTALLED_COUNTS}
    topk_rows: list[dict[str, Any]] = []
    flood_rows: list[dict[str, Any]] = []
    for n, caps in catalogues.items():
        if len(caps) != n:
            raise RuntimeError(f"catalogue size {len(caps)} != {n}")
        for query in QUERIES:
            top = inject_topk(query["text"], caps, k=k, ceiling=ceiling)
            topk_rows.append(_run_row(n, query, top))
            flood = inject_unbounded_flood(query["text"], caps)
            flood_rows.append(_run_row(n, query, flood))

    def tokens_for(rows: list[dict[str, Any]], n: int, qid: str) -> int:
        hits = [r for r in rows if r["installed_count"] == n and r["query_id"] == qid]
        if len(hits) != 1:
            raise RuntimeError(f"expected 1 row n={n} q={qid} got {len(hits)}")
        return int(hits[0]["injected_tokens"])

    def max_at(rows: list[dict[str, Any]], n: int) -> int:
        return max(int(r["injected_tokens"]) for r in rows if r["installed_count"] == n)

    def mean_at(rows: list[dict[str, Any]], n: int) -> float:
        xs = [int(r["injected_tokens"]) for r in rows if r["installed_count"] == n]
        return sum(xs) / float(len(xs))

    amb_topk = {n: tokens_for(topk_rows, n, "q-ambiguous") for n in INSTALLED_COUNTS}
    amb_flood = {n: tokens_for(flood_rows, n, "q-ambiguous") for n in INSTALLED_COUNTS}
    sub = is_sublinear(amb_topk)
    lin = is_linear_growth(amb_flood)
    at_500_max = max_at(topk_rows, 500)
    budget_held = at_500_max <= ceiling
    flood_500 = amb_flood[500]
    flood_exceeds = flood_500 > ceiling

    # Relevant-skill recall on labelled queries at every catalogue size.
    recall_rows = []
    for row in topk_rows:
        expect = row["expect_id"]
        if not expect:
            continue
        recall_rows.append(
            {
                "installed_count": row["installed_count"],
                "query_id": row["query_id"],
                "expect_id": expect,
                "hit": expect in row["admitted_ids"],
                "admitted_ids": row["admitted_ids"],
            }
        )
    recall_ok = all(r["hit"] for r in recall_rows)
    nomatch_ok = all(
        r["injected_tokens"] == 0 and not r["admitted_ids"]
        for r in topk_rows
        if r["query_id"] == "q-nomatch"
    )
    recount_ok = all(r["recount_ok"] for r in topk_rows + flood_rows)
    sha_ok = all(r["payload_sha256"] == r["payload_sha256_recomputed"] for r in topk_rows)

    raw_tokens = [int(r["injected_tokens"]) for r in topk_rows]
    band = moments(raw_tokens)
    per_n = {}
    for n in INSTALLED_COUNTS:
        xs = [int(r["injected_tokens"]) for r in topk_rows if r["installed_count"] == n]
        per_n[str(n)] = moments(xs)

    growth_curve = []
    for n in INSTALLED_COUNTS:
        amb = amb_topk[n]
        growth_curve.append(
            {
                "installed_count": n,
                "mean_injected_tokens": mean_at(topk_rows, n),
                "max_injected_tokens": max_at(topk_rows, n),
                "ambiguous_injected_tokens": amb,
                "tokens_per_installed": amb / float(n),
            }
        )

    tests = [
        {
            "id": "test_injected_tokens_stay_under_budget_at_500_capabilities",
            "result": "PASS" if budget_held else "FAIL",
            "ceiling": ceiling,
            "at_500_max_injected_tokens": at_500_max,
        },
        {
            "id": "test_growth_is_sublinear_in_the_installed_count",
            "result": "PASS" if sub["pass"] else "FAIL",
            "detail": sub,
        },
        {
            "id": "test_unbounded_flood_exceeds_budget_at_500",
            "result": "PASS" if flood_exceeds else "FAIL",
            "unbounded_at_500": flood_500,
        },
        {
            "id": "test_unbounded_flood_grows_linearly",
            "result": "PASS" if lin["pass"] else "FAIL",
            "detail": lin,
        },
        {
            "id": "test_labelled_relevant_skill_is_selected",
            "result": "PASS" if recall_ok else "FAIL",
        },
        {
            "id": "test_no_match_injects_nothing",
            "result": "PASS" if nomatch_ok else "FAIL",
        },
        {
            "id": "test_tokens_are_measured_from_payload_not_estimate",
            "result": "PASS" if recount_ok and sha_ok else "FAIL",
        },
    ]
    all_pass = all(t["result"] == "PASS" for t in tests)
    return {
        "k": k,
        "ceiling": ceiling,
        "installed_counts": list(INSTALLED_COUNTS),
        "topk_rows": topk_rows,
        "flood_rows": flood_rows,
        "growth_curve": growth_curve,
        "ambiguous_topk": amb_topk,
        "ambiguous_flood": amb_flood,
        "sublinear": sub,
        "linear_flood": lin,
        "budget_held": budget_held,
        "at_500_max_injected_tokens": at_500_max,
        "flood_500": flood_500,
        "flood_exceeds": flood_exceeds,
        "recall_ok": recall_ok,
        "nomatch_ok": nomatch_ok,
        "recount_ok": recount_ok,
        "sha_ok": sha_ok,
        "variance_band": {**band, "per_installed_count": per_n},
        "tests": tests,
        "all_pass": all_pass,
        "recall_rows": recall_rows,
    }
