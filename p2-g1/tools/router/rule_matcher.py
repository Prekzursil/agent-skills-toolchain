"""Deterministic rule matcher: 4 kinds × 13 labelled queries (IMP-0389)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

KINDS = ("exact", "prefix", "regex", "token")


@dataclass
class MatchResult:
    fired_row_ids: list[str]
    empty: bool
    model_calls: int = 0
    kind: str = ""


def builtin_table() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n = 0
    for kind in KINDS:
        for i in range(13):
            n += 1
            rid = f"R-{kind}-{i:02d}"
            needle = f"{kind}-needle-{i:02d}"
            rows.append(
                {
                    "id": rid,
                    "kind": kind,
                    "pattern": needle,
                    "mention": f"see also {kind}-needle-{(i + 1) % 13:02d}",
                }
            )
    assert len(rows) == 52
    return rows


def validate_table(table: list[dict[str, Any]]) -> None:
    ids = [r["id"] for r in table]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate row ids")
    if any(r.get("kind") not in KINDS for r in table):
        raise ValueError("unknown kind")


def _match_row(query_text: str, row: dict[str, Any]) -> bool:
    kind = row["kind"]
    pat = str(row["pattern"])
    if kind == "exact":
        return query_text == pat
    if kind == "prefix":
        if not query_text.startswith(pat):
            return False
        return len(query_text) == len(pat) or query_text[len(pat)] in "-_/:"
    if kind == "regex":
        return re.fullmatch(re.escape(pat), query_text) is not None
    if kind == "token":
        return pat in query_text.split()
    return False


def match_query(query: dict[str, Any], table: list[dict[str, Any]]) -> MatchResult:
    text = str(query.get("text") or "")
    fired = [row["id"] for row in table if _match_row(text, row)]
    return MatchResult(
        fired_row_ids=fired,
        empty=not fired,
        model_calls=0,
        kind=str(query.get("kind") or ""),
    )


def naive_payload_scan(query: dict[str, Any], table: list[dict[str, Any]]) -> list[str]:
    blob = " ".join(str(v) for v in query.values())
    return [row["id"] for row in table if str(row["pattern"]) in blob or str(row.get("mention") or "") in blob]


def kind_unit_queries(table: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for kind in KINDS:
        row = next(r for r in table if r["kind"] == kind)
        sibling = next(r for r in table if r["kind"] == kind and r["id"] != row["id"])
        text = row["pattern"]
        payload = f"{text} mention:{sibling['pattern']} {row['mention']}"
        out[kind] = {
            "kind": kind,
            "text": text,
            "payload": payload,
            "expected_row_ids": [row["id"]],
        }
    return out


def labelled_corpus(table: list[dict[str, Any]]) -> list[dict[str, Any]]:
    corpus: list[dict[str, Any]] = []
    by_kind: dict[str, list[dict[str, Any]]] = {k: [] for k in KINDS}
    for row in table:
        by_kind[row["kind"]].append(row)
    qid = 0
    for kind in KINDS:
        rows = by_kind[kind]
        # 8 hits + 5 empties = 13
        for i, row in enumerate(rows[:8]):
            qid += 1
            corpus.append(
                {
                    "query_id": f"Q-{kind}-{i:02d}",
                    "kind": kind,
                    "text": row["pattern"] if kind != "prefix" else row["pattern"] + "-suffix",
                    "expected_row_ids": [row["id"]],
                    "empty": False,
                }
            )
        for i in range(5):
            qid += 1
            corpus.append(
                {
                    "query_id": f"Q-{kind}-empty-{i:02d}",
                    "kind": kind,
                    "text": f"nomatch-{kind}-{i}",
                    "expected_row_ids": [],
                    "empty": True,
                }
            )
    for i in range(8):
        qid += 1
        corpus.append(
            {
                "query_id": f"Q-untyped-empty-{i:02d}",
                "kind": None,
                "text": f"untyped-nomatch-{i}",
                "expected_row_ids": [],
                "empty": True,
            }
        )
    if len(corpus) != 60:
        raise RuntimeError(f"corpus {len(corpus)} != 60")
    return corpus


def trace_corpus(corpus: list[dict[str, Any]], table: list[dict[str, Any]]) -> list[dict[str, Any]]:
    traces = []
    for query in corpus:
        result = match_query(query, table)
        label_ok = result.fired_row_ids == list(query.get("expected_row_ids") or [])
        traces.append(
            {
                "query_id": query["query_id"],
                "kind": query.get("kind"),
                "fired_row_ids": result.fired_row_ids,
                "empty": result.empty,
                "label_ok": label_ok,
                "model_calls": result.model_calls,
            }
        )
    return traces


__all__ = [
    "KINDS",
    "MatchResult",
    "builtin_table",
    "kind_unit_queries",
    "labelled_corpus",
    "match_query",
    "naive_payload_scan",
    "trace_corpus",
    "validate_table",
]
