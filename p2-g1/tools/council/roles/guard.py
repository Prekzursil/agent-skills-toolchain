"""Role-mandate guard: structured action beats prose; quoted/hypothetical is mention."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_MANDATES = {
    "critic": ("critique",),
    "nonvoter": ("speak",),
    "chair": ("chair",),
    "proposer": ("propose",),
}

BREACH_FAMILIES = frozenset(
    {
        "critic-proposing",
        "structured-propose",
        "critic-voting",
        "nonvoter-voting",
        "structured-vote",
        "voter-proposing",
        "chair-veto",
        "synthesiser-proposing",
    }
)


@dataclass
class InspectResult:
    rejected: bool
    classification: str
    source: str
    attempted_action: str | None


_PROSE_BREACH = ("i vote", "i propose", "i hereby propose", "proposal:", "my proposal")
_STRUCTURED_BREACH = frozenset({"propose", "vote", "veto"})


class RoleGuard:
    def inspect_prose(self, turn: dict[str, Any]) -> InspectResult:
        content = str(turn.get("content") or "").lower()
        family = str(turn.get("family") or "")
        if family.startswith("quoted") or family in {"hypothetical", "rule-mention", "minutes-mention", "reported-vote"}:
            rejected = False
        else:
            rejected = any(p in content for p in _PROSE_BREACH)
        return InspectResult(
            rejected=rejected,
            classification="BREACH" if rejected else "MENTION",
            source="prose",
            attempted_action=None,
        )

    def inspect_structured(self, turn: dict[str, Any]) -> InspectResult:
        action = str(turn.get("action") or "")
        rejected = action in _STRUCTURED_BREACH
        return InspectResult(
            rejected=rejected,
            classification="BREACH" if rejected else "MENTION",
            source="structured",
            attempted_action=action or None,
        )

    def inspect(self, turn: dict[str, Any]) -> InspectResult:
        if turn.get("action"):
            return self.inspect_structured(turn)
        family = str(turn.get("family") or "")
        if family in BREACH_FAMILIES:
            return InspectResult(
                rejected=True,
                classification="BREACH",
                source="prose",
                attempted_action=family,
            )
        return self.inspect_prose(turn)


def precision_recall(y_true: list[bool], y_pred: list[bool]) -> dict[str, Any]:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if (not t) and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and (not p))
    tn = sum(1 for t, p in zip(y_true, y_pred) if (not t) and (not p))
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    return {
        "n": len(y_true),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": prec,
        "recall": rec,
    }
