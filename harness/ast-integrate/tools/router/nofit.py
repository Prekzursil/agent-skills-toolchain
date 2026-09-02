"""No-fit router: terminal NO-CAPABILITY-FITS vs SELECTED. IMP-0396.

Every ``route()`` call returns a TERMINAL result: ``verdict`` is either
``SELECTED`` or ``NO-CAPABILITY-FITS`` and ``terminal`` is True, whatever the
input (None, empty, non-string, huge blob).  A weak lexical overlap below
``FIT_THRESHOLD`` is never promoted; the closest rejected capabilities are
reported so the refusal is explainable.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

VERDICT_SELECTED = "SELECTED"
VERDICT_NOFIT = "NO-CAPABILITY-FITS"
TERMINAL_VERDICTS = (VERDICT_SELECTED, VERDICT_NOFIT)
FIT_THRESHOLD = 0.5
MUTANT_THRESHOLD = 0.05
AUDIT_SEED = 396
AUDIT_SIZE = 100
CLOSEST_K = 3
CLOSEST_N = CLOSEST_K


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


def coerce_query(query: Any) -> str:
    """Render any input as the text the router actually scored (never raises)."""
    if isinstance(query, str):
        return query
    if query is None:
        return ""
    if isinstance(query, (bytes, bytearray)):
        return bytes(query).decode("utf-8", errors="replace")
    if isinstance(query, float) and (math.isnan(query) or math.isinf(query)):
        return ""
    try:
        return str(query)
    except Exception:  # pragma: no cover - defensive: __str__ may be hostile
        return ""


def _tokens(text: str) -> frozenset[str]:
    return frozenset(
        t.lower()
        for t in str(text).replace("/", " ").replace("-", " ").split()
        if t
    )


def _cap_bag(cap: dict[str, Any]) -> set[str]:
    bag: set[str] = set()
    for t in cap.get("triggers") or []:
        bag |= _tokens(t)
    bag |= _tokens(cap.get("capability_id") or "")
    bag |= _tokens(cap.get("description") or "")
    return bag


def _score(query: Any, cap: dict[str, Any]) -> float:
    if not isinstance(query, str) or not query.strip():
        return 0.0
    q = _tokens(query)
    if not q:
        return 0.0
    overlap = len(q & _cap_bag(cap))
    return overlap / len(q)


def rank(query: Any, caps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score every capability; ties break on capability_id so output is stable."""
    if not isinstance(query, str) or not query.strip():
        return [
            {"capability_id": cap.get("capability_id"), "score": 0.0, "matched_tokens": []}
            for cap in sorted(caps, key=lambda c: str(c.get("capability_id") or ""))
        ]
    q = _tokens(query)
    rows = []
    for cap in caps:
        matched = sorted(q & _cap_bag(cap))
        score = (len(matched) / len(q)) if q else 0.0
        rows.append(
            {
                "capability_id": cap.get("capability_id"),
                "score": score,
                "matched_tokens": matched,
            }
        )
    rows.sort(key=lambda r: (-r["score"], str(r["capability_id"] or "")))
    return rows


def _closest_rejected(ranked: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    return [
        {
            "capability_id": r["capability_id"],
            "score": r["score"],
            "matched_tokens": list(r["matched_tokens"]),
            "reason": "below-threshold",
        }
        for r in ranked
        if r["score"] < threshold
    ][:CLOSEST_N]


def route(query: Any, caps: list[dict[str, Any]], threshold: float | None = None) -> dict[str, Any]:
    """Route one query to a capability or refuse terminally.

    ``threshold`` defaults to the live ``FIT_THRESHOLD``; the mutation control
    passes a lowered value explicitly instead of mutating module state.
    """
    thr = FIT_THRESHOLD if threshold is None else float(threshold)
    if not isinstance(query, str) or not query.strip():
        return {
            "verdict": VERDICT_NOFIT,
            "terminal": True,
            "query": query,
            "capability_id": None,
            "score": 0.0,
            "best_score": 0.0,
            "ranked": [],
            "closest_rejected": [],
            "reason": "query is not a non-empty string; nothing to match",
        }
    ranked = rank(query, caps)
    best = ranked[0] if ranked else None
    best_score = float(best["score"]) if best else 0.0
    if best is not None and best_score >= thr:
        return {
            "verdict": VERDICT_SELECTED,
            "terminal": True,
            "query": query,
            "capability_id": best["capability_id"],
            "score": best_score,
            "best_score": best_score,
            "ranked": ranked,
            "closest_rejected": [],
            "reason": f"best score {best_score} >= FIT_THRESHOLD={thr}",
        }
    return {
        "verdict": VERDICT_NOFIT,
        "terminal": True,
        "query": query,
        "capability_id": None,
        "score": max(best_score, 0.0),
        "best_score": max(best_score, 0.0),
        "ranked": ranked,
        "closest_rejected": _closest_rejected(ranked, thr),
        "reason": f"best score {max(best_score, 0.0)} < FIT_THRESHOLD={thr}; not promoting a weak match",
    }


def is_terminal(result: dict[str, Any] | None) -> bool:
    return bool(result) and result.get("terminal") is True and result.get("verdict") in {
        VERDICT_SELECTED,
        VERDICT_NOFIT,
    }


def nofit_corpus_all_nofit(caps, queries, threshold: float | None = None) -> dict[str, Any]:
    """Every labelled no-fit query must come back NO-CAPABILITY-FITS."""
    thr = FIT_THRESHOLD if threshold is None else float(threshold)
    failures = []
    rows = []
    for q in queries:
        r = route(q, caps, threshold=thr)
        rows.append(
            {
                "query": coerce_query(q),
                "verdict": r["verdict"],
                "best_score": r["best_score"],
                "closest_rejected": r["closest_rejected"],
            }
        )
        if r.get("verdict") != VERDICT_NOFIT:
            failures.append({"query": coerce_query(q), "result": _jsonable(r)})
    return {
        "n": len(queries),
        "n_fail": len(failures),
        "threshold": thr,
        "pass": not failures,
        "failures": failures,
        "rows": rows,
    }


def _jsonable(result: dict[str, Any]) -> dict[str, Any]:
    out = dict(result)
    out["query"] = coerce_query(result.get("query"))
    return out


def audit_queries(extra=None, seed: int = AUDIT_SEED, size: int = AUDIT_SIZE) -> list[Any]:
    """Seeded mix of labelled queries plus adversarial fillers (empty/None/int/noise)."""
    rng = random.Random(seed)
    queries: list[Any] = list(extra or [])
    while len(queries) < size:
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
    return queries[:size]


def terminal_audit(caps, extra=None) -> dict[str, Any]:
    queries = audit_queries(extra)
    terminal = 0
    empty_or_null = 0
    non_terminal = 0
    verdicts: dict[str, int] = {}
    failures = []
    examples = []
    for q in queries:
        r = route(q, caps)
        if r is None or r.get("verdict") in {None, ""}:
            empty_or_null += 1
            failures.append({"query": coerce_query(q), "result": r})
            continue
        if not is_terminal(r):
            non_terminal += 1
            failures.append({"query": coerce_query(q), "result": _jsonable(r)})
            continue
        terminal += 1
        verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
        if len(examples) < 5:
            examples.append(
                {
                    "query": coerce_query(q),
                    "verdict": r["verdict"],
                    "terminal": True,
                    "best_score": r["best_score"],
                }
            )
    return {
        "n": len(queries),
        "terminal": terminal,
        "non_terminal": non_terminal,
        "empty_or_null": empty_or_null,
        "verdicts": verdicts,
        "pass": terminal == len(queries) and empty_or_null == 0 and non_terminal == 0,
        "failures": failures,
        "seed": AUDIT_SEED,
        "examples": examples,
    }


def threshold_mutation_control(caps, queries, mutant_threshold: float = MUTANT_THRESHOLD) -> dict[str, Any]:
    """Both-states control: the no-fit corpus is green at the production
    threshold and must turn red when the threshold is lowered enough for a weak
    overlap to be promoted.  Module state is never mutated."""
    production = nofit_corpus_all_nofit(caps, queries)
    mutant = nofit_corpus_all_nofit(caps, queries, threshold=mutant_threshold)
    injected = []
    for q in queries:
        prod = route(q, caps)
        mut = route(q, caps, threshold=mutant_threshold)
        if prod["verdict"] == VERDICT_NOFIT and mut["verdict"] == VERDICT_SELECTED:
            injected.append(
                {
                    "query": coerce_query(q),
                    "production_verdict": prod["verdict"],
                    "production_best": prod["best_score"],
                    "mutant_verdict": mut["verdict"],
                    "mutant_selected": mut["capability_id"],
                    "mutant_score": mut["best_score"],
                }
            )
    mutant["injected_weak_matches"] = len(injected)
    silent_on_good = bool(production["pass"])
    fired_on_bad = (not mutant["pass"]) and bool(injected)
    return {
        "production": production,
        "mutant": mutant,
        "injected": injected,
        "silent_on_good_state": silent_on_good,
        "fired_on_bad_state": fired_on_bad,
        "pass": silent_on_good and fired_on_bad,
        # legacy keys kept for older callers
        "leaked": [row["query"] for row in injected],
        "threshold": float(mutant_threshold),
    }


def adversarial_inputs() -> list[Any]:
    """21 hostile inputs: None, empty, whitespace, non-strings, bytes, NaN/inf,
    only-stopwords, CJK, control bytes, emoji, an 8k blob and an opaque object."""
    return [
        None,
        "",
        "   ",
        "\t\n",
        0,
        -1,
        3.14,
        float("nan"),
        float("inf"),
        True,
        b"bytes are not text",
        b"",
        [],
        {},
        ("tuple",),
        "the and of a",
        "\u3053\u3093\u306b\u3061\u306f\u4e16\u754c",
        "x" * 8000,
        "\x00\x00",
        "\U0001f525" * 50,
        object(),
    ]


def silence_hunt(caps) -> dict[str, Any]:
    """Independent hunt for a silent (non-terminal / empty / raising) return."""
    inputs = adversarial_inputs()
    hits = []
    for q in inputs:
        try:
            r = route(q, caps)
        except Exception as exc:  # a raise IS a non-terminal return
            hits.append({"query": repr(q)[:80], "error": f"{type(exc).__name__}: {exc}"})
            continue
        if r is None or r.get("verdict") in {None, ""}:
            hits.append({"query": repr(q)[:80], "result": "empty-or-null"})
        elif not is_terminal(r):
            hits.append({"query": repr(q)[:80], "result": _jsonable(r)})
    passed = not hits
    return {
        "reviewer_id": "IMP-0396-silence-hunt",
        "independent": True,
        "method": (
            f"{len(inputs)} adversarial inputs (None, empty, whitespace, non-strings, "
            "bytes, NaN, only-stopwords, CJK, 8k blob) routed through nofit.route; "
            "a hit is any non-terminal or empty/null return"
        ),
        "attempts": len(inputs),
        "non_terminal_hits": hits,
        "verdict": "PASS" if passed else "FAIL",
        "pass": passed,
    }
