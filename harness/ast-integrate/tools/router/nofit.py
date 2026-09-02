"""No-fit router: terminal NO-CAPABILITY-FITS vs SELECTED. IMP-0396."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

VERDICT_SELECTED = "SELECTED"
VERDICT_NOFIT = "NO-CAPABILITY-FITS"
FIT_THRESHOLD = 0.5


def load_index(path: Path | str) -> list[dict[str, Any]]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    caps = list(doc.get("capabilities") or [])
    threshold = doc.get("fit_threshold")
    if isinstance(threshold, (int, float)):
        global FIT_THRESHOLD
        FIT_THRESHOLD = float(threshold)
    return caps


def load_queries(path: Path | str) -> list[str]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for row in doc.get("queries") or []:
        if isinstance(row, str):
            out.append(row)
        elif isinstance(row, dict) and row.get("query") is not None:
            out.append(row["query"])
    return out


def _tokens(text: str) -> frozenset[str]:
    return frozenset(
        t.lower()
        for t in str(text).replace("/", " ").replace("-", " ").split()
        if t
    )


def _score(query: Any, cap: dict[str, Any]) -> float:
    if not isinstance(query, str) or not query.strip():
        return 0.0
    q = _tokens(query)
    bag: set[str] = set()
    for t in cap.get("triggers") or []:
        bag |= _tokens(t)
    bag |= _tokens(cap.get("capability_id") or "")
    bag |= _tokens(cap.get("description") or "")
    if not q:
        return 0.0
    overlap = len(q & bag)
    return overlap / len(q)


def route(query: Any, caps: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip():
        return {
            "verdict": VERDICT_NOFIT,
            "terminal": True,
            "query": query,
            "capability_id": None,
            "score": 0.0,
        }
    best = None
    best_score = -1.0
    for cap in caps:
        s = _score(query, cap)
        if s > best_score:
            best_score = s
            best = cap
    if best is not None and best_score >= FIT_THRESHOLD:
        return {
            "verdict": VERDICT_SELECTED,
            "terminal": True,
            "query": query,
            "capability_id": best.get("capability_id"),
            "score": best_score,
        }
    return {
        "verdict": VERDICT_NOFIT,
        "terminal": True,
        "query": query,
        "capability_id": None,
        "score": max(best_score, 0.0),
    }


def is_terminal(result: dict[str, Any] | None) -> bool:
    return bool(result) and result.get("terminal") is True and result.get("verdict") in {
        VERDICT_SELECTED,
        VERDICT_NOFIT,
    }


def nofit_corpus_all_nofit(caps, queries) -> dict[str, Any]:
    failures = []
    for q in queries:
        r = route(q, caps)
        if r.get("verdict") != VERDICT_NOFIT:
            failures.append({"query": q, "result": r})
    return {
        "n": len(queries),
        "n_fail": len(failures),
        "threshold": FIT_THRESHOLD,
        "pass": not failures,
        "failures": failures,
    }


def terminal_audit(caps, extra=None) -> dict[str, Any]:
    extra = list(extra or [])
    rng = random.Random(396)
    queries: list[Any] = list(extra)
    while len(queries) < 100:
        kind = rng.randrange(5)
        if kind == 0:
            queries.append("")
        elif kind == 1:
            queries.append(None)
        elif kind == 2:
            queries.append(rng.randint(0, 99))
        elif kind == 3:
            queries.append(" ".join(rng.choice(["foo", "bar", "weather", "cake"]) for _ in range(4)))
        else:
            queries.append("xyzzy not a capability at all")
    queries = queries[:100]
    terminal = 0
    empty_or_null = 0
    non_terminal = 0
    verdicts: dict[str, int] = {}
    failures = []
    for q in queries:
        r = route(q, caps)
        if r is None or r.get("verdict") in {None, ""}:
            empty_or_null += 1
            failures.append({"query": q, "result": r})
            continue
        if not is_terminal(r):
            non_terminal += 1
            failures.append({"query": q, "result": r})
            continue
        terminal += 1
        verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
    return {
        "n": 100,
        "terminal": terminal,
        "non_terminal": non_terminal,
        "empty_or_null": empty_or_null,
        "verdicts": verdicts,
        "pass": terminal == 100 and empty_or_null == 0 and non_terminal == 0,
        "failures": failures,
        "seed": 396,
    }


def threshold_mutation_control(caps, queries) -> dict[str, Any]:
    global FIT_THRESHOLD
    old = FIT_THRESHOLD
    FIT_THRESHOLD = 0.05
    try:
        leaked = []
        for q in queries:
            r = route(q, caps)
            if r.get("verdict") == VERDICT_SELECTED:
                leaked.append(q)
        return {"pass": bool(leaked), "leaked": leaked, "threshold": FIT_THRESHOLD}
    finally:
        FIT_THRESHOLD = old
