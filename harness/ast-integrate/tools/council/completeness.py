"""Min-coverage completeness score. Padding and undeclared answers add no credit."""
from __future__ import annotations

import re
from typing import Any

FORMULA_ID = "min-coverage-v1"
THRESHOLD = 0.90
MIN_CONTENT_TOKENS = 8
SPEC_EXPRESSION = "min(subquestion_coverage, category_coverage, evidence_coverage)"
SPEC_LINE_ABSENT = "SPEC_LINE_ABSENT"
SPEC_LINE_CITATION = "catalog stopping example completeness_score >= 0.90"


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", text or "")


def score_output(objective: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    sq = [s["id"] for s in objective.get("subquestions") or []]
    cats = list(objective.get("required_categories") or [])
    evc = list(objective.get("evidence_classes") or [])
    answers = list(output.get("answers") or [])
    evidence = list(output.get("evidence") or [])
    covered_sq = set()
    covered_cat = set()
    ignored = 0
    word_count = 0
    for ans in answers:
        body = str(ans.get("body") or "")
        word_count += len(_words(body))
        sid = ans.get("subquestion_id")
        if sid in sq:
            if len(_words(body)) >= MIN_CONTENT_TOKENS:
                covered_sq.add(sid)
            covered_cat.update(c for c in (ans.get("categories") or []) if c in cats)
        else:
            ignored += 1
    covered_ev = set()
    for item in evidence:
        klass = item.get("evidence_class")
        payload = str(item.get("payload") or "")
        if klass in evc and payload:
            cites_ok = True
            covered_ev.add(klass)
    sq_c = (len(covered_sq) / len(sq)) if sq else 1.0
    cat_c = (len(covered_cat) / len(cats)) if cats else 1.0
    ev_c = (len(covered_ev) / len(evc)) if evc else 1.0
    score = min(sq_c, cat_c, ev_c)
    unverified = score < THRESHOLD
    gate_fires = score >= THRESHOLD
    return {
        "score": score,
        "unverified": unverified,
        "gate_fires": gate_fires,
        "may_bind_stopping_rule": gate_fires and not unverified,
        "components": {
            "subquestions": sq_c,
            "categories": cat_c,
            "evidence": ev_c,
        },
        "word_count": word_count,
        "ignored_undeclared_answers": ignored,
        "formula_id": FORMULA_ID,
    }
