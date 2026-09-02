"""Aider-class file-graph ranking and cold tag-scan timing (local, no networkx)."""

from __future__ import annotations

import random
import re
import time
from typing import Any

DEF_RE = re.compile(r"^\s*(def|class|function|fn|func)\s+(\w+)", re.M)
REF_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]{2,})\s*\(", re.M)
TAG_BLOB_BYTES = 4110
TAG_THRESHOLD_S = 5.0
PAGERANK_THRESHOLD_S = 2.0
SEED = 7


def _pagerank(
    n: int,
    edges: list[tuple[int, int, float]],
    pers: list[float],
    damping: float = 0.85,
    iters: int = 20,
) -> list[float]:
    out_w = [0.0] * n
    adj: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    for src, dst, weight in edges:
        out_w[src] += weight
        adj[src].append((dst, weight))
    rank = [1.0 / n] * n
    pers_sum = sum(pers) or 1.0
    pers_n = [p / pers_sum for p in pers]
    for _ in range(iters):
        nxt = [(1.0 - damping) * pers_n[i] for i in range(n)]
        dangling = 0.0
        for i in range(n):
            if out_w[i] == 0:
                dangling += rank[i]
            else:
                share = damping * rank[i]
                inv = 1.0 / out_w[i]
                for dst, weight in adj[i]:
                    nxt[dst] += share * (weight * inv)
        add = damping * dangling / n
        for i in range(n):
            nxt[i] += add
        rank = nxt
    return rank


def synth_graph(n: int, avg_deg: int = 8, seed: int = SEED) -> tuple[list, list]:
    rng = random.Random(seed)
    edges: list[tuple[int, int, float]] = []
    chat_n = max(2, n // 50)
    for src in range(n):
        k = max(1, int(rng.gauss(avg_deg, 2)))
        for _ in range(k):
            dst = rng.randrange(n)
            if dst == src:
                continue
            weight = 1.0 + rng.random() * 4.0
            if src < chat_n:
                weight *= 50.0
            edges.append((src, dst, weight))
    pers = [0.0] * n
    for i in range(max(1, n // 100)):
        pers[i] = 1.0
    return edges, pers


def pagerank_ms(n: int) -> dict[str, Any]:
    edges, pers = synth_graph(n)
    t0 = time.perf_counter()
    rank = _pagerank(n, edges, pers)
    ms = (time.perf_counter() - t0) * 1000.0
    return {
        "n_files": n,
        "n_edges": len(edges),
        "ms": round(ms, 1),
        "seconds": round(ms / 1000.0, 4),
        "rank0": round(rank[0], 8),
    }


def _tag_blob() -> str:
    rng = random.Random(1)
    names = [f"sym_{i}" for i in range(40)]
    lines: list[str] = []
    while sum(len(x) + 1 for x in lines) < 4096:
        if rng.random() < 0.15:
            lines.append(f"def {rng.choice(names)}(x):")
            lines.append("    return x")
        else:
            lines.append(f"    y = {rng.choice(names)}(1)")
    return "\n".join(lines) + "\n"


def tag_scan_ms(n_files: int, blob: str | None = None) -> dict[str, Any]:
    text = blob if blob is not None else _tag_blob()
    t0 = time.perf_counter()
    n_defs = 0
    n_refs = 0
    for _ in range(n_files):
        n_defs += len(DEF_RE.findall(text))
        n_refs += len(REF_RE.findall(text))
    ms = (time.perf_counter() - t0) * 1000.0
    return {
        "n_files": n_files,
        "blob_bytes": len(text.encode("utf-8")),
        "ms": round(ms, 1),
        "seconds": round(ms / 1000.0, 4),
        "defs": n_defs,
        "refs": n_refs,
        "method": "regex-tag-extract-repeated-4kib-blob",
    }


def interpolate_n_at_seconds(rows: list[dict[str, Any]], seconds: float) -> int:
    rates = [r["ms"] / r["n_files"] for r in rows if r["n_files"] > 0]
    if not rates:
        raise ValueError("no rates")
    ms_per_file = sum(rates) / len(rates)
    return int(round((seconds * 1000.0) / ms_per_file))


def scale_report() -> dict[str, Any]:
    """Live local scale report. Fast enough for named-probe re-run (<10s)."""
    blob = _tag_blob()
    tag_rows = [tag_scan_ms(8000, blob), tag_scan_ms(16000, blob)]
    pr_rows = [pagerank_ms(10000), pagerank_ms(20000)]
    n_tag_5s = interpolate_n_at_seconds(tag_rows, TAG_THRESHOLD_S)
    n_pr_2s = interpolate_n_at_seconds(pr_rows, PAGERANK_THRESHOLD_S)
    return {
        "host_method": (
            "In-process regex tag extract over a repeated 4KiB synthetic file "
            "(stand-in for tree-sitter tags) plus personalized power-iteration "
            "PageRank on a synthetic file graph (Aider-class: files as nodes, "
            "chat-file edge multiplier 50x). tree-sitter itself is NOT invoked."
        ),
        "tag_scan": {
            "threshold_s": TAG_THRESHOLD_S,
            "rows": tag_rows,
            "n_files_at_threshold": n_tag_5s,
            "approx_source_mb_at_threshold": round(n_tag_5s * TAG_BLOB_BYTES / 1e6, 1),
        },
        "pagerank": {
            "threshold_s": PAGERANK_THRESHOLD_S,
            "rows": pr_rows,
            "n_files_at_threshold": n_pr_2s,
        },
        "limiting_stage": "cold-tag-extraction-not-pagerank",
        "too_slow_repository_size": {
            "n_files": n_tag_5s,
            "file_bytes": TAG_BLOB_BYTES,
            "criterion": (
                f"cold regex tag extract exceeds {TAG_THRESHOLD_S}s interactive "
                "budget on this host"
            ),
        },
    }
