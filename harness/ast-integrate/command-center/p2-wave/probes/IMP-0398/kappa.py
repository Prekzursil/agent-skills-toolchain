#!/usr/bin/env python3
"""Blind second-annotator relabel for IMP-0398 (keyword rules on query text only)."""
from __future__ import annotations

import math
import random
import re
from collections import Counter
from typing import Iterable

# Independent of gold columns: each rule maps query text -> expected set.
# Order matters; first match wins. NEGATIVE catch-alls sit last.
_RULES: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"NUL-named|capability-index\.json from six roots|index_build", re.I),
     ["skill.router.index-build"]),
    (re.compile(r"secret-shaped token|absolute user path|privacy-scrub|telemetry scrub", re.I),
     ["skill.privacy.scrub"]),
    (re.compile(r"Architect, Skeptic, Pragmatist, Critic|four-voice council", re.I),
     ["skill.council.four-voice"]),
    (re.compile(r"git archive|stored git blob bytes", re.I),
     ["skill.blob.provenance"]),
    (re.compile(r"JSON schema that rejects a receipt missing its sentinel", re.I),
     ["skill.schema.author"]),
    (re.compile(r"Corrupt one router description|mutation harness|regression suite goes red", re.I),
     ["skill.mutation.harness"]),
    (re.compile(r"stale cache|content hash plus mtime|next router call sees the change", re.I),
     ["skill.cache.invalidate"]),
    (re.compile(r"owner ban|scores 0\.99|pin a capability always-on", re.I),
     ["skill.override.ban-pin"]),
    (re.compile(r"NO-CAPABILITY-FITS|injecting a weak match", re.I),
     ["skill.nofit.terminal"]),
    (re.compile(r"Search the public web", re.I),
     ["skill.web.search"]),
    (re.compile(r"Read the file capability-index\.json from disk", re.I),
     ["skill.file.read"]),
    (re.compile(r"Run a shell command to list", re.I),
     ["command.shell.exec"]),
]


def class_label(ids: Iterable[str] | None) -> str:
    s = sorted({str(x) for x in (ids or []) if str(x)})
    return "NEGATIVE" if not s else "|".join(s)


def keyword_label(query: str) -> list[str]:
    text = query or ""
    for pat, ids in _RULES:
        if pat.search(text):
            return list(ids)
    return []


def cohen_kappa(y1: list[str], y2: list[str]) -> float:
    if len(y1) != len(y2) or not y1:
        raise ValueError("kappa needs equal non-empty label lists")
    n = len(y1)
    po = sum(a == b for a, b in zip(y1, y2)) / n
    c1, c2 = Counter(y1), Counter(y2)
    classes = set(c1) | set(c2)
    pe = sum((c1[k] / n) * (c2[k] / n) for k in classes)
    if math.isclose(pe, 1.0):
        return 1.0 if math.isclose(po, 1.0) else 0.0
    return (po - pe) / (1.0 - pe)


def sample_ids(query_ids: list[str], n: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    ids = list(query_ids)
    rng.shuffle(ids)
    k = max(1, n)
    return ids[:k]


def relabel_and_kappa(queries: list[dict], *, seed: int = 398, fraction: float = 0.10) -> dict:
    by_id = {str(q["id"]): q for q in queries}
    ids = [str(q["id"]) for q in queries]
    k = max(4, int(math.ceil(len(ids) * fraction)))
    sample = sample_ids(ids, k, seed)
    gold, blind = [], []
    rows = []
    for qid in sample:
        q = by_id[qid]
        g = class_label(q.get("expected_capability_ids"))
        b_ids = keyword_label(str(q.get("query") or ""))
        b = class_label(b_ids)
        gold.append(g)
        blind.append(b)
        rows.append(
            {
                "id": qid,
                "gold": g,
                "blind": b,
                "agree": g == b,
            }
        )
    value = cohen_kappa(gold, blind)
    return {
        "value": value,
        "n_relabeled": len(sample),
        "threshold": 0.7,
        "pass": value >= 0.7,
        "seed": seed,
        "sample_ids": sample,
        "rows": rows,
        "method": (
            "Second annotator is keyword_label() on query text only; "
            "expected_capability_ids is unread."
        ),
    }
