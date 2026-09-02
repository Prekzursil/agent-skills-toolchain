#!/usr/bin/env python3
"""Deterministic first-stage capability router (no model call).

Matches IMP-0389 matcher kinds: keyword substring, glob path, cwd prefix,
tool-verb. Every non-zero score names the trigger rows that fired. Empty
top-k is a typed NO-CAPABILITY-FITS verdict, never a silent null.
"""
from __future__ import annotations

import fnmatch
import re
from pathlib import PurePosixPath
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP = frozenset(
    {
        "this",
        "that",
        "with",
        "from",
        "the",
        "and",
        "for",
        "are",
        "was",
        "were",
        "have",
        "has",
        "been",
        "into",
        "over",
        "after",
        "before",
        "today",
        "what",
        "which",
        "does",
        "not",
        "use",
        "from",
        "only",
        "than",
        "then",
        "also",
        "skill",
        "plugin",
    }
)
KEYWORD_WEIGHT = 3.0
GLOB_WEIGHT = 2.0
CWD_WEIGHT = 2.0
VERB_WEIGHT = 2.5
LEXICAL_WEIGHT = 0.25


def tokens(text: str) -> set[str]:
    return {
        t
        for t in TOKEN_RE.findall((text or "").lower())
        if len(t) >= 4 and t not in STOP
    }


def _glob_hit(pattern: str, path: str) -> bool:
    rel = (path or "").replace("\\", "/").lstrip("/")
    pat = (pattern or "").replace("\\", "/")
    if not pat or not rel:
        return False
    if fnmatch.fnmatch(rel, pat):
        return True
    name = rel.rsplit("/", 1)[-1]
    if fnmatch.fnmatch(name, pat.rsplit("/", 1)[-1]):
        return True
    try:
        return PurePosixPath(rel).match(pat)
    except (ValueError, OSError):
        return False


def score_capability(task: dict[str, Any], cap: dict[str, Any]) -> dict[str, Any]:
    trig = cap.get("triggers") or {}
    prompt = str(task.get("prompt") or "")
    prompt_l = prompt.lower()
    paths = [str(p) for p in (task.get("paths") or [])]
    cwd = str(task.get("cwd") or "")
    verbs = [str(v).lower() for v in (task.get("tool_verbs") or [])]
    fired: list[str] = []
    score = 0.0

    for kw in trig.get("keywords") or []:
        needle = str(kw).lower()
        if needle and needle in prompt_l:
            score += KEYWORD_WEIGHT
            fired.append(f"keyword:{kw}")

    for pat in trig.get("globs") or []:
        if any(_glob_hit(str(pat), p) for p in paths):
            score += GLOB_WEIGHT
            fired.append(f"glob:{pat}")

    for prefix in trig.get("cwd_prefixes") or []:
        pre = str(prefix)
        if pre and (cwd == pre or cwd.startswith(pre.rstrip("/") + "/")):
            score += CWD_WEIGHT
            fired.append(f"cwd:{prefix}")

    for verb in trig.get("verbs") or []:
        if str(verb).lower() in verbs:
            score += VERB_WEIGHT
            fired.append(f"verb:{verb}")

    desc_toks = tokens(str(cap.get("description") or ""))
    prompt_toks = tokens(prompt)
    overlap = desc_toks & prompt_toks
    if overlap:
        lex = LEXICAL_WEIGHT * len(overlap)
        score += lex
        fired.append("lexical:" + ",".join(sorted(overlap)))

    return {
        "capability_id": cap["capability_id"],
        "kind": cap.get("kind"),
        "score": round(score, 4),
        "fired": fired,
    }


def route_task(
    task: dict[str, Any],
    index: dict[str, Any],
    *,
    k: int | None = None,
    threshold: float | None = None,
) -> dict[str, Any]:
    caps = list(index.get("capabilities") or [])
    k = int(k if k is not None else index.get("k") or 3)
    threshold = float(
        threshold if threshold is not None else index.get("score_threshold") or 1.0
    )
    ranked = [score_capability(task, cap) for cap in caps]
    ranked.sort(key=lambda row: (-float(row["score"]), str(row["capability_id"])))
    above = [row for row in ranked if float(row["score"]) >= threshold]
    topk = above[:k]
    if topk:
        verdict = "SELECTED"
    else:
        verdict = "NO-CAPABILITY-FITS"
    return {
        "task_id": task["id"],
        "is_control": bool(task.get("is_control")),
        "expected_capability": task.get("expected_capability"),
        "expected_verdict": task.get("expected_verdict"),
        "verdict": verdict,
        "k": k,
        "threshold": threshold,
        "topk": topk,
        "topk_ids": [row["capability_id"] for row in topk],
        "near_misses": [
            row for row in ranked if row["capability_id"] not in {r["capability_id"] for r in topk}
        ][:5],
    }
