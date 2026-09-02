"""Evidence-or-cut classifier and ranking for A8 polish items.

Rule: an item with no observed error behind it is COSMETIC, not UNPROVEN.
Survivors (ERROR-REDUCING) are ranked by occurrence_count / effort_units.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CLAIM = HERE / "fixtures" / "a8-claimed-organizing-principle.json"

ALLOWED = frozenset({"ERROR-REDUCING", "COSMETIC"})


def load_items() -> list[dict[str, Any]]:
    doc = json.loads(CLAIM.read_text(encoding="utf-8"))
    items = doc.get("polish_items")
    if not isinstance(items, list) or len(items) < 3:
        raise RuntimeError("A8 polish_items missing or short")
    return items


def classify(
    items: list[dict[str, Any]],
    tally: dict[str, int],
) -> dict[str, Any]:
    classified: list[dict[str, Any]] = []
    for raw in items:
        eid = str(raw["id"])
        err = str(raw["error_class"])
        effort = int(raw["effort_units"])
        if effort < 1:
            raise RuntimeError(f"{eid} effort_units must be >= 1")
        count = int(tally.get(err, 0))
        if count < 0:
            raise RuntimeError(f"{eid} negative count")
        klass = "ERROR-REDUCING" if count >= 1 else "COSMETIC"
        ratio = (count / effort) if count >= 1 else 0.0
        classified.append(
            {
                "id": eid,
                "title": str(raw["title"]),
                "error_class": err,
                "effort_units": effort,
                "occurrence_count": count,
                "class": klass,
                "reduction_per_effort": ratio,
                "settling_evidence": (
                    f"Re-count live {err} observations; item stays ERROR-REDUCING "
                    f"iff count>=1. A zero count must be COSMETIC, never UNPROVEN."
                ),
            }
        )

    for row in classified:
        if row["class"] not in ALLOWED:
            return {
                "ok": False,
                "why": f"{row['id']}-illegal-class:{row['class']}",
            }
        if row["occurrence_count"] == 0 and row["class"] != "COSMETIC":
            return {
                "ok": False,
                "why": f"{row['id']}-zero-count-not-cosmetic",
            }
        if row["occurrence_count"] >= 1 and row["class"] != "ERROR-REDUCING":
            return {
                "ok": False,
                "why": f"{row['id']}-positive-count-not-error-reducing",
            }

    survivors = [r for r in classified if r["class"] == "ERROR-REDUCING"]
    ranked = sorted(
        survivors,
        key=lambda r: (-float(r["reduction_per_effort"]), r["id"]),
    )
    for i in range(1, len(ranked)):
        if float(ranked[i]["reduction_per_effort"]) > float(
            ranked[i - 1]["reduction_per_effort"]
        ):
            return {"ok": False, "why": "ranking-not-monotonic"}

    cosmetic = [r["id"] for r in classified if r["class"] == "COSMETIC"]
    return {
        "ok": True,
        "why": (
            f"error-reducing={len(survivors)} cosmetic={len(cosmetic)} "
            f"ranked={[r['id'] for r in ranked]}"
        ),
        "items": classified,
        "cosmetic_ids": cosmetic,
        "surviving_ranked": ranked,
        "organizing_principle_would_fund_cosmetic": len(cosmetic) >= 1,
        "computed_not_asserted": True,
    }


def reject_unproven(items: list[dict[str, Any]]) -> tuple[bool, str]:
    """Return False when any item is labelled UNPROVEN (evidence-or-cut)."""
    if not items:
        return False, "items-empty"
    for row in items:
        klass = str(row.get("class") or "")
        if klass == "UNPROVEN":
            return False, f"{row.get('id')}-UNPROVEN"
        if klass not in ALLOWED:
            return False, f"{row.get('id')}-illegal-class:{klass}"
        if int(row.get("occurrence_count") or 0) == 0 and klass != "COSMETIC":
            return False, f"{row.get('id')}-zero-count-not-cosmetic"
    return True, "no-UNPROVEN"


def classify_live(tally: dict[str, int]) -> dict[str, Any]:
    return classify(load_items(), tally)
