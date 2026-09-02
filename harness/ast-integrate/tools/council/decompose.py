"""Split/recompose independent compound questions (IMP-0355).

A compound question is a list of clauses, each binding one or more variables
(``binds``) and optionally declaring inputs it consumes (``needs``).  The
dependency pass runs BEFORE any split and fires when one clause consumes what
another produces.  It does not trust the ``needs`` annotation alone: the
consumer's text is scanned for the producer's bound-variable tokens
(``token-bind``) and for causal cues that reference the producer's content
(``causal-need``), so a fixture whose ``needs`` was stripped still fires.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

REASON_NEEDS_BIND = "needs-bind"
REASON_TOKEN_BIND = "token-bind"
REASON_CAUSAL_NEED = "causal-need"

# Cues that mark a clause as conditioned on another answer.
_CAUSAL_CUES: tuple[str, ...] = (
    "given",
    "based on",
    "depending on",
    "depends on",
    "derived from",
    "according to",
    "in light of",
    "using the",
    "once we know",
    "after we know",
)

_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for",
        "from", "how", "in", "is", "it", "of", "on", "or", "our", "set",
        "should", "that", "the", "this", "to", "we", "what", "which", "who",
        "why", "with", "you", "your", "given", "based", "depending", "depends",
        "derived", "according", "light", "using", "once", "after", "know",
        "many", "much", "when", "where", "if", "than", "then", "there",
    }
)


@dataclass
class Claim:
    id: str
    text: str = ""
    supported_by: list[str] = field(default_factory=list)
    value: Any = None
    variable: str = ""


@dataclass
class ComposedAnswer:
    question_id: str
    text: str
    claims: list[Claim]
    sub_ids: list[str]
    invented: bool = False


@dataclass
class SupportResult:
    ok: bool
    unsupported_ids: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DependencyEdge:
    """``consumer`` uses something ``producer`` binds; ``reason`` names the detector."""

    producer: str
    consumer: str
    reason: str
    evidence: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "producer": self.producer,
            "consumer": self.consumer,
            "reason": self.reason,
            "evidence": list(self.evidence),
        }


@dataclass
class DependencyResult:
    """Outcome of the dependency pass over one compound question."""

    question_id: str
    fired: bool
    edges: list[DependencyEdge] = field(default_factory=list)
    interacting_ids: list[str] = field(default_factory=list)
    order: list[str] = field(default_factory=list)
    cyclic: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "fired": self.fired,
            "edges": [e.as_dict() for e in self.edges],
            "interacting_ids": list(self.interacting_ids),
            "order": list(self.order),
            "cyclic": self.cyclic,
        }


@dataclass
class SplitResult:
    """Outcome of ``split``: accepted only when the clauses are independent
    (or when a sequenced plan was explicitly allowed)."""

    question_id: str
    accepted: bool
    subquestions: list[dict[str, Any]] = field(default_factory=list)
    dependency_pass_fired: bool = False
    dependencies: DependencyResult | None = None
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "accepted": self.accepted,
            "subquestions": [dict(s) for s in self.subquestions],
            "dependency_pass_fired": self.dependency_pass_fired,
            "dependencies": self.dependencies.as_dict() if self.dependencies else None,
            "reason": self.reason,
        }


def load_claim(raw: dict[str, Any], cid: str, supported_by: str = "") -> Claim:
    return Claim(
        id=str(raw.get("id") or cid),
        text=str(raw.get("text") or ""),
        supported_by=[supported_by] if supported_by else list(raw.get("supported_by") or []),
        value=raw.get("value"),
        variable=str(raw.get("variable") or ""),
    )


def load_sub_answer(raw: dict[str, Any]) -> dict[str, Any]:
    return dict(raw)


def inject_unsupported_claim(composed: ComposedAnswer, overclaim: dict[str, Any]) -> ComposedAnswer:
    extra = load_claim(overclaim if isinstance(overclaim, dict) else {"id": "invented", "text": str(overclaim)}, "invented")
    extra.supported_by = []
    return ComposedAnswer(
        question_id=composed.question_id,
        text=composed.text + " " + extra.text,
        claims=list(composed.claims) + [extra],
        sub_ids=list(composed.sub_ids),
        invented=True,
    )


def support_check(composed: ComposedAnswer, answers: list[dict[str, Any]]) -> SupportResult:
    covered: set[str] = set()
    for ans in answers:
        for c in ans.get("claims") or []:
            covered.add(str(c.get("id") or c.get("variable") or ""))
            if c.get("text"):
                covered.add(c["text"])
    unsupported = []
    rows = []
    for claim in composed.claims:
        ok = bool(claim.supported_by) or claim.id in covered or claim.text in covered
        if not ok:
            unsupported.append(claim.id)
        rows.append({"claim_id": claim.id, "ok": ok, "covered_by": claim.supported_by})
    return SupportResult(ok=not unsupported, unsupported_ids=unsupported, rows=rows)


# --------------------------------------------------------------------------- #
# Dependency pass
# --------------------------------------------------------------------------- #


def _variable_tokens(variable: str) -> list[str]:
    """``checkout.p99`` -> ``['checkout', 'p99']`` (lower-case, split on ._- and space)."""
    return [t for t in re.split(r"[._\-\s/]+", str(variable).lower()) if len(t) >= 2]


def _text_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text).lower())


def _content_tokens(text: str) -> set[str]:
    return {t for t in _text_tokens(text) if len(t) >= 2 and t not in _STOPWORDS}


def _causal_cue(text: str) -> str:
    low = " " + " ".join(_text_tokens(text)) + " "
    for cue in _CAUSAL_CUES:
        if f" {cue} " in low:
            return cue
    return ""


def _clause_id(clause: dict[str, Any], index: int) -> str:
    return str(clause.get("id") or f"clause-{index + 1}")


def _topological_order(ids: list[str], edges: list[DependencyEdge]) -> tuple[list[str], bool]:
    """Kahn's algorithm over producer->consumer edges; ``cyclic`` when it stalls."""
    indeg = {cid: 0 for cid in ids}
    out: dict[str, list[str]] = {cid: [] for cid in ids}
    seen: set[tuple[str, str]] = set()
    for e in edges:
        key = (e.producer, e.consumer)
        if key in seen or e.producer not in indeg or e.consumer not in indeg:
            continue
        seen.add(key)
        out[e.producer].append(e.consumer)
        indeg[e.consumer] += 1
    ready = [cid for cid in ids if indeg[cid] == 0]
    order: list[str] = []
    while ready:
        cur = ready.pop(0)
        order.append(cur)
        for nxt in out[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
    return order, len(order) != len(ids)


def detect_dependencies(question: dict[str, Any]) -> DependencyResult:
    """Find clause pairs where one clause consumes what another binds.

    Three detectors, every one recorded as its own edge:

    * ``needs-bind``  - consumer declares ``needs`` intersecting producer ``binds``.
    * ``token-bind``  - every token of a producer-bound variable appears in the
      consumer text (``checkout.p99`` inside "given the measured checkout p99").
    * ``causal-need`` - consumer text carries a causal cue (given / based on /
      depending on ...) and shares at least two content tokens with the producer.

    The annotation is not trusted on its own: the second and third detectors
    run on the text, so stripping ``needs`` does not silence the pass.
    """
    clauses = list(question.get("clauses") or [])
    ids = [_clause_id(cl, i) for i, cl in enumerate(clauses)]
    edges: list[DependencyEdge] = []
    for i, prod in enumerate(clauses):
        prod_id = ids[i]
        prod_binds = [str(v) for v in (prod.get("binds") or [])]
        prod_content = _content_tokens(prod.get("text") or "")
        for j, cons in enumerate(clauses):
            if i == j:
                continue
            cons_id = ids[j]
            cons_text = str(cons.get("text") or "")
            cons_tokens = set(_text_tokens(cons_text))
            needs = {str(v) for v in (cons.get("needs") or [])}
            hit = sorted(needs & set(prod_binds))
            if hit:
                edges.append(DependencyEdge(prod_id, cons_id, REASON_NEEDS_BIND, hit))
            for var in prod_binds:
                toks = _variable_tokens(var)
                if toks and all(t in cons_tokens for t in toks):
                    edges.append(DependencyEdge(prod_id, cons_id, REASON_TOKEN_BIND, [var]))
            cue = _causal_cue(cons_text)
            if cue:
                shared = sorted(prod_content & _content_tokens(cons_text))
                if len(shared) >= 2:
                    edges.append(
                        DependencyEdge(prod_id, cons_id, REASON_CAUSAL_NEED, [cue, *shared])
                    )
    interacting = sorted({e.producer for e in edges} | {e.consumer for e in edges})
    order, cyclic = _topological_order(ids, edges)
    return DependencyResult(
        question_id=str(question.get("id") or ""),
        fired=bool(edges),
        edges=edges,
        interacting_ids=interacting,
        order=order,
        cyclic=cyclic,
    )


def _subquestion(clause: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": _clause_id(clause, index),
        "text": clause.get("text"),
        "domain": clause.get("domain"),
        "binds": list(clause.get("binds") or []),
        "needs": list(clause.get("needs") or []),
    }


def split(question: dict[str, Any], require_independent: bool = True) -> SplitResult:
    """Run the dependency pass, then split into sub-questions.

    With ``require_independent`` (the default) a question whose dependency pass
    fired is REFUSED: ``accepted`` is False and ``subquestions`` is empty, so the
    caller cannot fan the clauses out to independent councils.  With
    ``require_independent=False`` a dependent question is accepted as a
    SEQUENCED plan (sub-questions in topological order) unless it is cyclic.
    """
    clauses = list(question.get("clauses") or [])
    qid = str(question.get("id") or "")
    deps = detect_dependencies(question)
    if len(clauses) < 2:
        return SplitResult(qid, False, [], deps.fired, deps, "not-compound")
    subs = [_subquestion(cl, i) for i, cl in enumerate(clauses)]
    if not deps.fired:
        return SplitResult(qid, True, subs, False, deps, "independent")
    if require_independent:
        return SplitResult(qid, False, [], True, deps, "coupled-refused")
    if deps.cyclic:
        return SplitResult(qid, False, [], True, deps, "cyclic-refused")
    by_id = {s["id"]: s for s in subs}
    ordered = [by_id[cid] for cid in deps.order if cid in by_id]
    return SplitResult(qid, True, ordered, True, deps, "sequenced")


def run_independent_packet(question: dict[str, Any], answers: list[dict[str, Any]]) -> dict[str, Any]:
    clauses = list(question.get("clauses") or [])
    subquestions = [_subquestion(cl, i) for i, cl in enumerate(clauses)]
    # Independent packet: the dependency pass must stay silent.
    dependency_pass_fired = detect_dependencies(question).fired
    by_sub = {a.get("sub_id"): a for a in answers}
    support_rows = []
    ok = True
    for cl in clauses:
        ans = by_sub.get(cl.get("id"))
        claims = list((ans or {}).get("claims") or [])
        covered = [c.get("id") for c in claims]
        row_ok = bool(ans) and bool(claims)
        if not row_ok:
            ok = False
        support_rows.append(
            {
                "claim_id": cl.get("id"),
                "covered_by": covered,
                "ok": row_ok,
            }
        )
    support_ok = ok and len(subquestions) >= 2 and not dependency_pass_fired
    composed_claims = []
    composed_text_parts = []
    sub_ids = []
    for a in answers:
        sub_ids.append(a.get("sub_id"))
        composed_text_parts.append(a.get("text") or "")
        for c in a.get("claims") or []:
            composed_claims.append(
                {
                    "id": c.get("id"),
                    "text": c.get("text"),
                    "value": c.get("value"),
                    "variable": c.get("variable"),
                    "supported_by": [a.get("sub_id")],
                }
            )
    return {
        "ok": support_ok,
        "split": {
            "subquestions": subquestions,
            "dependency_pass_fired": dependency_pass_fired,
        },
        "support": {"ok": support_ok, "rows": support_rows},
        "composed": {
            "text": " ".join(composed_text_parts),
            "claims": composed_claims,
            "sub_ids": sub_ids,
        },
    }
