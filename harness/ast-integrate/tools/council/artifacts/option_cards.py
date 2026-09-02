"""Idea-to-option-card promotion. Maturity bar does not read held-out labels."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CARD_REQUIRED_FIELDS = (
    "card_id",
    "source_idea_id",
    "title",
    "mechanism",
    "canonical_mechanism_id",
    "cost",
    "risk",
    "evidence",
    "actionability",
    "source",
)

CHECK_ORDER = (
    "mechanism-empty",
    "mechanism-slogan",
    "cost-missing",
    "cost-not-numeric",
    "cost-unit",
    "risk-missing",
    "risk-unknown",
    "risk-severity",
    "evidence-empty",
    "evidence-blank-ref",
    "title-equals-mechanism",
)

COST_UNITS = {"engineering-days", "engineer-days", "hours"}
SEV = {"low", "medium", "high", "critical"}
SLOGANS = {"be better", "innovate faster", "try harder"}


def _mech(idea: dict[str, Any]) -> str:
    return str(idea.get("mechanism") or "").strip()


def drop_reason(idea: dict[str, Any]) -> str | None:
    mech = _mech(idea)
    if not mech:
        return "mechanism-empty"
    if mech.casefold() in SLOGANS or len(mech.split()) < 6:
        return "mechanism-slogan"
    cost = idea.get("cost")
    if not isinstance(cost, dict):
        return "cost-missing"
    est = cost.get("estimate")
    if not isinstance(est, (int, float)):
        return "cost-not-numeric"
    if str(cost.get("unit") or "") not in COST_UNITS:
        return "cost-unit"
    risk = idea.get("risk")
    if not isinstance(risk, dict):
        return "risk-missing"
    fm = str(risk.get("failure_mode") or "").strip().casefold()
    if not fm or fm == "unknown":
        return "risk-unknown"
    if str(risk.get("severity") or "").casefold() not in SEV:
        return "risk-severity"
    evidence = idea.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return "evidence-empty"
    for item in evidence:
        if not isinstance(item, dict) or not str(item.get("ref") or "").strip():
            return "evidence-blank-ref"
    title = str(idea.get("title") or "").strip()
    if title and title == str(idea.get("mechanism") or "").strip():
        return "title-equals-mechanism"
    return None


def _card(idea: dict[str, Any], idx: int) -> dict[str, Any]:
    return {
        "card_id": f"CARD-{idx:02d}",
        "source_idea_id": idea["idea_id"],
        "title": idea.get("title"),
        "mechanism": idea.get("mechanism"),
        "canonical_mechanism_id": idea.get("canonical_mechanism_id"),
        "cost": idea.get("cost"),
        "risk": idea.get("risk"),
        "evidence": idea.get("evidence"),
        "actionability": idea.get("actionability"),
        "source": idea.get("source"),
    }


@dataclass
class PromotionResult:
    cards: list[dict[str, Any]]
    dropped: list[dict[str, Any]]
    n_promoted: int
    promotion_rate: float

    def dropped_by_reason(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for row in self.dropped:
            out[row["drop_reason"]] = out.get(row["drop_reason"], 0) + 1
        return out


def promote(ideas: list[dict[str, Any]], evidence_root: Path | None = None) -> PromotionResult:
    cards: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for idea in ideas:
        reason = drop_reason(idea)
        if reason:
            dropped.append({"idea_id": idea.get("idea_id"), "drop_reason": reason})
        else:
            cards.append(_card(idea, len(cards) + 1))
    n = len(ideas) or 1
    dropped.sort(key=lambda r: str(r.get("idea_id") or ""))
    return PromotionResult(
        cards=cards,
        dropped=dropped,
        n_promoted=len(cards),
        promotion_rate=len(cards) / n,
    )


def validate_card(card: dict[str, Any]) -> list[str]:
    return [f"missing:{f}" for f in CARD_REQUIRED_FIELDS if f not in card or card.get(f) in (None, "")]


def field_completeness_audit(cards: list[dict[str, Any]]) -> dict[str, Any]:
    incomplete = [c.get("card_id") for c in cards if validate_card(c)]
    return {
        "all_complete": not incomplete,
        "n_incomplete": len(incomplete),
        "incomplete": incomplete,
    }


def inject_incomplete_card(card: dict[str, Any], drop_field: str) -> dict[str, Any]:
    out = dict(card)
    out.pop(drop_field, None)
    return out
