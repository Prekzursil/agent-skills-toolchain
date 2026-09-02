"""Split/recompose independent compound questions (IMP-0355)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
