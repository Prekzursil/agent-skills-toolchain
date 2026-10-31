"""Split/recompose independent compound questions (IMP-0355)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable


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


def run_independent_packet(question: dict[str, Any], answers: list[dict[str, Any]]) -> dict[str, Any]:
    clauses = list(question.get("clauses") or [])
    subquestions = []
    for cl in clauses:
        subquestions.append(
            {
                "id": cl.get("id"),
                "text": cl.get("text"),
                "domain": cl.get("domain"),
                "binds": cl.get("binds") or [],
                "needs": cl.get("needs") or [],
            }
        )
    # Independent packet: no clause needs another.
    dependency_pass_fired = any(cl.get("needs") for cl in clauses)
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


# --- Dependency detection and split gating (IMP-0355 probe2 contract) ---

_CAUSAL_MARKERS: tuple[str, ...] = (
    "given the",
    "based on",
    "depending on",
    "depends on",
    "as measured",
    "according to",
    "referencing",
)

_BIND_STOP = {
    "the", "and", "for", "with", "from", "this", "that", "what", "which",
    "who", "how", "many", "much", "should", "set", "give", "given", "is",
    "are", "of", "in", "on", "to", "a", "an", "does", "do", "we", "be",
    "by", "as", "at", "it", "its", "our", "us", "per", "or", "if", "text",
    "id", "domain", "needs", "binds", "clauses", "answers", "claims",
    "value", "variable",
}


class DependencyEdge:
    def __init__(self, a_id: str, b_id: str, reason: str, detail: str = "") -> None:
        self.a_id = a_id
        self.b_id = b_id
        self.reason = reason
        self.detail = detail

    def __repr__(self) -> str:
        return f"DependencyEdge({self.a_id}->{self.b_id}:{self.reason})"


class DependencyReport:
    def __init__(self, edges: list[DependencyEdge]) -> None:
        self.edges = edges
        self.fired = bool(edges)
        seen: set[str] = set()
        for e in edges:
            seen.add(e.a_id)
            seen.add(e.b_id)
        self.interacting_ids = sorted(seen)


class SplitResult:
    def __init__(
        self,
        accepted: bool,
        dependency_pass_fired: bool,
        subquestions: list[dict[str, Any]],
        question_id: Any = None,
        require_independent: bool = True,
    ) -> None:
        self.accepted = accepted
        self.dependency_pass_fired = dependency_pass_fired
        self.subquestions = subquestions
        self.question_id = question_id
        self.require_independent = require_independent


def _bind_tokens(binds: Iterable[Any] | None) -> set[str]:
    out: set[str] = set()
    for b in binds or []:
        out |= {
            w
            for w in re.findall(r"[a-z0-9]+", str(b).lower())
            if len(w) >= 3 and w not in _BIND_STOP
        }
    return out


def _content_words(text: str) -> set[str]:
    return {
        w
        for w in re.findall(r"[a-z0-9]+", str(text).lower())
        if len(w) >= 3 and w not in _BIND_STOP
    }


def detect_dependencies(question: dict[str, Any]) -> DependencyReport:
    """Detect cross-sub-question coupling BEFORE a split, on three signals:
    declared needs hitting a sibling's bind (needs-bind), one clause's text
    referencing a variable another clause binds (token-bind -- deliberate:
    annotations are not trusted, so the detector must not depend on needs[]),
    and a causal marker plus a bind reference (causal-need).
    """
    clauses = [c for c in (question.get("clauses") or []) if isinstance(c, dict)]
    edges: list[DependencyEdge] = []
    for i, a in enumerate(clauses):
        for b in clauses[i + 1:]:
            binds_a = set(a.get("binds") or [])
            binds_b = set(b.get("binds") or [])
            needs_a = set(a.get("needs") or [])
            needs_b = set(b.get("needs") or [])
            if needs_b & binds_a:
                edges.append(DependencyEdge(a["id"], b["id"], "needs-bind",
                                            f"{sorted(needs_b & binds_a)} needed by {b['id']}"))
            if needs_a & binds_b:
                edges.append(DependencyEdge(b["id"], a["id"], "needs-bind",
                                            f"{sorted(needs_a & binds_b)} needed by {a['id']}"))
            tokens_a = _bind_tokens(binds_a)
            tokens_b = _bind_tokens(binds_b)
            words_a = _content_words(a.get("text") or "")
            words_b = _content_words(b.get("text") or "")
            ref_b_to_a = tokens_a & words_b
            ref_a_to_b = tokens_b & words_a
            if ref_b_to_a or ref_a_to_b or (tokens_a & tokens_b):
                detail = ",".join(sorted(ref_b_to_a | ref_a_to_b | (tokens_a & tokens_b)))
                edges.append(DependencyEdge(a["id"], b["id"], "token-bind", detail))
                low_b = str(b.get("text") or "").lower()
                low_a = str(a.get("text") or "").lower()
                if any(m in low_b for m in _CAUSAL_MARKERS) and ref_b_to_a:
                    edges.append(DependencyEdge(a["id"], b["id"], "causal-need", detail))
                if any(m in low_a for m in _CAUSAL_MARKERS) and ref_a_to_b:
                    edges.append(DependencyEdge(b["id"], a["id"], "causal-need", detail))
    return DependencyReport(edges)


def split(
    question: dict[str, Any],
    require_independent: bool = True,
) -> SplitResult:
    """Split into subquestions; refuse when a coupled question demands independence."""
    deps = detect_dependencies(question)
    accepted = (not deps.fired) if require_independent else True
    subs: list[dict[str, Any]] = []
    if accepted:
        for cl in question.get("clauses") or []:
            if not isinstance(cl, dict):
                continue
            subs.append(
                {
                    "id": cl.get("id"),
                    "text": cl.get("text"),
                    "domain": cl.get("domain"),
                    "binds": list(cl.get("binds") or []),
                    "needs": list(cl.get("needs") or []),
                }
            )
    return SplitResult(
        accepted=accepted,
        dependency_pass_fired=deps.fired,
        subquestions=subs,
        question_id=question.get("id"),
        require_independent=require_independent,
    )
