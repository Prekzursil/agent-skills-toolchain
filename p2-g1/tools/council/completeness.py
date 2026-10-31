"""Min-three-axis declared-coverage completeness score (TST-0282).

Formula min-three-axis-declared-coverage-v1:

    completeness_score = min(subquestion_coverage, category_coverage,
                             evidence_class_coverage)

where each ratio is covered-declared / declared. A declared item is covered
only by a qualifying record: a subquestion answer needs >= MIN_CONTENT_TOKENS
non-stop, non-padding content tokens; an evidence class is covered only when
a record CITES that class. Extra undeclared volume adds no credit (padding
cannot buy score). Empty declared lists are NOT-CHECKED and must never gate.
"""
from __future__ import annotations

import re
from typing import Any

FORMULA_ID = "min-three-axis-declared-coverage-v1"
THRESHOLD = 0.90
MIN_CONTENT_TOKENS = 8

_STOPWORDS = frozenset(
    """a an and are as at be been being but by for from has have i in is it
    its of on or per that the their them then there these they this those to
    was were will with would you your""".split()
)

_PADDING_MARKERS = frozenset(
    {"etc", "above", "as", "see", "note", "tbd", "todo", "lorem", "ipsum"}
)


def content_tokens(text: str) -> list[str]:
    """Non-stop, non-padding content tokens (the qualifying-record test)."""
    toks = re.findall(r"[A-Za-z0-9_]+", str(text or "").lower())
    return [t for t in toks if t not in _STOPWORDS and t not in _PADDING_MARKERS]


def score_output(objective: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    """Score one output against one objective's declared coverage axes."""
    sq = [str(s["id"]) for s in (objective.get("subquestions") or []) if isinstance(s, dict) and s.get("id")]
    cats = [str(c) for c in (objective.get("required_categories") or [])]
    evc = [str(e) for e in (objective.get("evidence_classes") or [])]
    answers = list(output.get("answers") or [])
    evidence = list(output.get("evidence") or [])

    covered_sq: set[str] = set()
    covered_cat: set[str] = set()
    ignored = 0
    word_count = 0
    for ans in answers:
        body = str(ans.get("body") or "")
        toks = content_tokens(body)
        word_count += len(re.findall(r"[A-Za-z0-9_]+", body))
        sid = str(ans.get("subquestion_id"))
        if sid in sq:
            if len(toks) >= MIN_CONTENT_TOKENS:
                covered_sq.add(sid)
            covered_cat.update(
                c for c in (ans.get("categories") or []) if str(c) in cats
            )
        else:
            ignored += 1

    covered_ev: set[str] = set()
    for item in evidence:
        klass = str(item.get("evidence_class"))
        cites = item.get("cites") or item.get("citation") or item.get("anchor")
        if klass in evc and cites:
            covered_ev.add(klass)

    sq_c = (len(covered_sq) / len(sq)) if sq else None
    cat_c = (len(covered_cat) / len(cats)) if cats else None
    ev_c = (len(covered_ev) / len(evc)) if evc else None

    empty_axes = [name for name, v in (("subquestions", sq_c), ("categories", cat_c), ("evidence_classes", ev_c)) if v is None]
    declared = [v for v in (sq_c, cat_c, ev_c) if v is not None]
    score = min(declared) if declared else 0.0
    status = "NOT-CHECKED" if empty_axes else "SCORED"
    unverified = score < THRESHOLD
    gate_fires = score >= THRESHOLD and not empty_axes
    return {
        "score": score,
        "status": status,
        "empty_axes": empty_axes,
        "unverified": unverified,
        "gate_fires": gate_fires,
        "may_bind_stopping_rule": gate_fires and not unverified,
        "components": {
            "subquestions": sq_c,
            "categories": cat_c,
            "evidence_classes": ev_c,
        },
        "word_count": word_count,
        "ignored_undeclared_answers": ignored,
        "formula_id": FORMULA_ID,
        "threshold": THRESHOLD,
    }
