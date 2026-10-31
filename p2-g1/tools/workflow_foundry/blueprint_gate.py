"""Promotion gate: UNKNOWN-NEEDS-PROBE cannot enter the blueprint library."""
from __future__ import annotations

from typing import Any, Mapping

UNKNOWN = "UNKNOWN-NEEDS-PROBE"


class PromotionBlocked(Exception):
    def __init__(self, classification: str, reason: str) -> None:
        self.classification = classification
        self.reason = reason
        super().__init__(reason)


def promote(candidate: Mapping[str, Any], library: dict[str, Any]) -> dict[str, Any]:
    cls = str(candidate.get("classification") or "")
    if cls == UNKNOWN:
        raise PromotionBlocked(
            cls,
            f"{UNKNOWN} cannot be promoted; notes are ignored until a settling probe terminates",
        )
    library.setdefault("blueprints", []).append(dict(candidate))
    return {"promoted": True, "blocked": False, "id": candidate.get("id")}


def try_promote(candidate: Mapping[str, Any], library: dict[str, Any]) -> dict[str, Any]:
    try:
        out = promote(candidate, library)
        return {"promoted": True, "blocked": False, **out}
    except PromotionBlocked as exc:
        return {
            "promoted": False,
            "blocked": True,
            "classification": exc.classification,
            "reason": exc.reason,
        }
