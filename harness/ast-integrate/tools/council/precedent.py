"""Precedent retrieval from prior councils (IMP-0258)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "to",
        "of",
        "in",
        "on",
        "for",
        "and",
        "or",
        "be",
        "is",
        "as",
        "by",
        "it",
        "if",
        "not",
        "with",
        "from",
        "that",
        "this",
        "should",
        "must",
        "may",
        "can",
        "does",
        "are",
        "was",
        "were",
    }
)


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text or "") if t.lower() not in STOP and len(t) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    return len(a & b) / float(len(union)) if union else 0.0


def _char_ngrams(text: str, n: int = 3) -> set[str]:
    s = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()
    compact = s.replace(" ", "")
    if len(compact) < n:
        return {compact} if compact else set()
    return {compact[i : i + n] for i in range(len(compact) - n + 1)}


def _dice(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return 2.0 * len(a & b) / float(len(a) + len(b))


def _score(query: str, council: dict[str, Any]) -> float:
    blob = " ".join(
        [
            str(council.get("question") or ""),
            str(council.get("decision") or ""),
            " ".join(str(t) for t in (council.get("tags") or [])),
        ]
    )
    j = _jaccard(_tokens(query), _tokens(blob))
    d = _dice(_char_ngrams(query), _char_ngrams(blob))
    return 0.6 * j + 0.4 * d


def load_corpus(path: Path | str) -> list[dict[str, Any]]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(doc, list):
        return [c for c in doc if isinstance(c, dict)]
    rows = doc.get("councils") if isinstance(doc, dict) else None
    return [c for c in (rows or []) if isinstance(c, dict)]


def load_eval_spec(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _marker_for(council: dict[str, Any]) -> dict[str, Any] | None:
    marker = council.get("supersession_marker")
    if isinstance(marker, dict) and marker:
        return dict(marker)
    status = str(council.get("status") or "").upper()
    if status == "SUPERSEDED":
        return {
            "status": "SUPERSEDED",
            "superseded_by": council.get("superseded_by"),
            "reason": council.get("supersession_reason"),
            "declared_at": council.get("superseded_at"),
        }
    return None


def retrieve(query: str, corpus: list[dict[str, Any]], *, k: int = 5, threshold: float = 0.18) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in corpus:
        s = _score(query, row)
        if s >= threshold:
            hit = dict(row)
            hit["score"] = s
            marker = _marker_for(row)
            if marker is not None:
                hit["supersession_marker"] = marker
            scored.append((s, hit))
    scored.sort(key=lambda x: (-x[0], str(x[1].get("council_id") or "")))
    return [h for _, h in scored[:k]]


def evaluate(spec: dict[str, Any], corpus: list[dict[str, Any]]) -> dict[str, Any]:
    recall_rows = []
    retrieved_n = 0
    for item in spec.get("repeated") or []:
        query = str(item.get("query") or "")
        must = [str(x) for x in (item.get("must_retrieve") or [])]
        hits = retrieve(query, corpus)
        ids = [str(h.get("council_id") or h.get("id") or "") for h in hits]
        ok = all(mid in ids for mid in must)
        if ok:
            retrieved_n += 1
        recall_rows.append({"query": query, "must": must, "ids": ids, "ok": ok})
    n_recall = len(recall_rows)
    fp_rows = []
    fps = 0
    for item in spec.get("novel") or []:
        query = str(item.get("query") or "")
        hits = retrieve(query, corpus, threshold=0.32)
        fp = bool(hits)
        if fp:
            fps += 1
        fp_rows.append(
            {
                "query": query,
                "false_positive": fp,
                "ids": [str(h.get("council_id") or h.get("id") or "") for h in hits],
            }
        )
    n_fp = len(fp_rows)
    return {
        "corpus_size": len(corpus),
        "recall": {
            "n": n_recall,
            "retrieved": retrieved_n,
            "recall": (retrieved_n / float(n_recall)) if n_recall else 1.0,
            "rows": recall_rows,
        },
        "false_positives": {
            "n": n_fp,
            "false_positives": fps,
            "false_positive_rate": (fps / float(n_fp)) if n_fp else 0.0,
            "rows": fp_rows,
        },
    }


def check_supersession_markers(hits: list[dict[str, Any]], corpus: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {str(c.get("council_id") or c.get("id") or ""): c for c in corpus}
    violations: list[dict[str, Any]] = []
    for hit in hits:
        hid = str(hit.get("council_id") or hit.get("id") or "")
        src = by_id.get(hid) or {}
        src_status = str(src.get("status") or "").upper()
        marker = hit.get("supersession_marker")
        if src_status == "SUPERSEDED":
            if not isinstance(marker, dict) or not marker:
                violations.append({"id": hid, "reason": "missing-marker"})
                continue
            status = str(marker.get("status") or "").upper()
            if status == "CURRENT" or status == "":
                violations.append({"id": hid, "reason": "unmarked-superseded"})
            elif status != "SUPERSEDED":
                violations.append({"id": hid, "reason": "unmarked-superseded"})
        elif isinstance(marker, dict) and str(marker.get("status") or "").upper() == "SUPERSEDED":
            if src_status != "SUPERSEDED":
                violations.append({"id": hid, "reason": "false-superseded-marker"})
    fires = bool(violations)
    return {"ok": not fires, "fires": fires, "violations": violations}


def strip_markers(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for hit in hits:
        row = dict(hit)
        row.pop("supersession_marker", None)
        out.append(row)
    return out


def relabel_superseded_as_current(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for hit in hits:
        row = dict(hit)
        marker = dict(row.get("supersession_marker") or {})
        if str(marker.get("status") or "").upper() == "SUPERSEDED":
            marker["status"] = "CURRENT"
            row["supersession_marker"] = marker
        out.append(row)
    return out


__all__ = [
    "check_supersession_markers",
    "evaluate",
    "load_corpus",
    "load_eval_spec",
    "relabel_superseded_as_current",
    "retrieve",
    "strip_markers",
]
