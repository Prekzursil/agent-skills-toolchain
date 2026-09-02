"""Min-coverage completeness score. Padding and undeclared answers add no credit.

completeness_score = min(subquestion_coverage, category_coverage, evidence_coverage)
where each ratio is covered-declared / declared.  A declared item is covered only
by a qualifying record: an answer for a declared subquestion carrying at least
MIN_CONTENT_TOKENS non-stop, non-padding content tokens; a category tagged on such
a qualifying answer; an evidence class whose item has a payload AND is cited by a
qualifying answer.  Extra undeclared volume is ignored.  An axis with no declared
items is NOT-CHECKED (excluded from the min); when nothing is declared at all the
score is None, the result is unverified and the gate must not fire.

The scorer never reads rater labels: it only sees ``objective`` and ``output``.
"""
from __future__ import annotations

import re
from typing import Any

FORMULA_ID = "min-coverage-v1"
THRESHOLD = 0.90
MIN_CONTENT_TOKENS = 8
SPEC_EXPRESSION = "min(subquestion_coverage, category_coverage, evidence_coverage)"
SPEC_LINE_ABSENT = "SPEC_LINE_ABSENT"
SPEC_LINE_CITATION = "catalog stopping example completeness_score >= 0.90"

NOT_CHECKED = None

_STOPWORDS = frozenset(
    """
    a an the and or but if then else of to in on at by for with from as is are was
    were be been being it its this that these those there here not no yes ok sure
    do does did done so such than too very can may might must shall should will
    would i you he she we they them his her our your their my me us
    """.split()
)

_PADDING_TOKENS = frozenset(
    """
    lorem ipsum dolor sit amet consectetur adipiscing elit sed eiusmod tempor
    incididunt ut labore et dolore magna aliqua placeholder padding filler asdf
    qwerty xxx dummy spam blah boilerplate paddingtext aaaa bbbb cccc tbd todo
    """.split()
)


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", text or "")


def content_tokens(text: str) -> list[str]:
    """Tokens that can earn coverage credit: not stop-words, not padding lexicon,
    not bare digits, and at least two characters long."""
    out = []
    for tok in _words(text):
        low = tok.lower()
        if len(low) < 2 or low.isdigit():
            continue
        if low in _STOPWORDS or low in _PADDING_TOKENS:
            continue
        out.append(low)
    return out


def _ratio(covered: set[str], declared: list[str]) -> float | None:
    if not declared:
        return NOT_CHECKED
    return len(covered) / len(declared)


def score_output(objective: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    sq = [str(s.get("id")) for s in (objective.get("subquestions") or []) if isinstance(s, dict)]
    cats = [str(c) for c in (objective.get("required_categories") or [])]
    evc = [str(e) for e in (objective.get("evidence_classes") or [])]
    answers = [a for a in (output.get("answers") or []) if isinstance(a, dict)]
    evidence = [e for e in (output.get("evidence") or []) if isinstance(e, dict)]

    covered_sq: set[str] = set()
    covered_cat: set[str] = set()
    cited_ids: set[str] = set()
    ignored = 0
    word_count = 0
    for ans in answers:
        body = str(ans.get("body") or "")
        word_count += len(_words(body))
        sid = ans.get("subquestion_id")
        if sid not in sq:
            ignored += 1
            continue
        if len(content_tokens(body)) < MIN_CONTENT_TOKENS:
            continue
        covered_sq.add(str(sid))
        covered_cat.update(str(c) for c in (ans.get("categories") or []) if str(c) in cats)
        cited_ids.update(str(c) for c in (ans.get("cites") or []))

    covered_ev: set[str] = set()
    for item in evidence:
        klass = item.get("evidence_class")
        payload = str(item.get("payload") or "")
        item_id = str(item.get("id") or "")
        if klass in evc and payload.strip() and item_id and item_id in cited_ids:
            covered_ev.add(str(klass))

    sq_c = _ratio(covered_sq, sq)
    cat_c = _ratio(covered_cat, cats)
    ev_c = _ratio(covered_ev, evc)
    checked = [c for c in (sq_c, cat_c, ev_c) if c is not None]
    score = min(checked) if checked else NOT_CHECKED
    if score is None:
        unverified = True
        gate_fires = False
    else:
        unverified = score < THRESHOLD
        gate_fires = score >= THRESHOLD
    return {
        "score": score,
        "unverified": unverified,
        "gate_fires": gate_fires,
        "may_bind_stopping_rule": gate_fires and not unverified,
        "not_checked": score is None,
        "components": {
            "subquestions": sq_c,
            "categories": cat_c,
            "evidence": ev_c,
        },
        "word_count": word_count,
        "ignored_undeclared_answers": ignored,
        "formula_id": FORMULA_ID,
    }
