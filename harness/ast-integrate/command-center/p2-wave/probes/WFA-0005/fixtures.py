"""Planted records and the lying-counts histogram fixture.

Plants are classified ADOPT-AS-IS on purpose: Signal A will not count them as
unused values; Signal B must still fire from does/mechanisms/notes.
"""
from __future__ import annotations

from typing import Any

from vocabulary import RULES, UNUSED_VALUES, VOCABULARY_15

DECOY_ID = "plant.decoy.adopt-as-is"


def _plant(value: str) -> dict[str, Any]:
    tokens = RULES[value]["all_tokens"]
    slug = value.lower().replace("_", "-")
    return {
        "id": f"plant.{slug}",
        "classification": "ADOPT-AS-IS",
        "does": (
            f"Planted record that obviously warrants {value}. {tokens[0]}. "
            "This sentence exists so the search cannot be a classification recount."
        ),
        "mechanisms": [tokens[1], f"decision-rule plant for {value}"],
        "notes": f"WFA-0005 planted positive control for {value}.",
        "family": "Z-plant",
        "license": "UNKNOWN" if value == "CLEAN-ROOM-REIMPLEMENT" else "MIT",
    }


def planted_records() -> list[dict[str, Any]]:
    rows = [_plant(v) for v in UNUSED_VALUES]
    rows.append(
        {
            "id": DECOY_ID,
            "classification": "ADOPT-AS-IS",
            "does": (
                "MIT-licensed leaf workflow on the chosen control plane; "
                "adopt as-is without wrapping."
            ),
            "mechanisms": ["single leaf step", "no sibling orchestration"],
            "notes": "Negative control: must not match any unused-value rule.",
            "family": "Z-plant",
            "license": "MIT",
        }
    )
    return rows


def planted_by_id() -> dict[str, dict[str, Any]]:
    return {str(r["id"]): r for r in planted_records()}


def plant_id_for(value: str) -> str:
    return f"plant.{value.lower().replace('_', '-')}"


def lying_counts_registry() -> dict[str, Any]:
    """counts.TRANSLATE=99 while no candidate is classified TRANSLATE."""
    used_cycle = [
        "ADOPT-AS-IS",
        "UNKNOWN-NEEDS-PROBE",
        "DISTILL",
        "RETIRE",
        "ADOPT-WITH-WRAPPER",
        "REPAIR",
        "EXTEND",
        "MERGE",
        "SPECIALIZE",
    ]
    candidates: list[dict[str, Any]] = []
    for i, label in enumerate(used_cycle, start=1):
        candidates.append(
            {
                "id": f"hist.{i:02d}.{label}",
                "classification": label,
                "does": f"ordinary {label} record with no unused-value tokens",
                "mechanisms": ["leaf"],
                "notes": "histogram fixture",
            }
        )
    return {
        "classification_vocabulary": list(VOCABULARY_15),
        "counts": {
            "ADOPT-AS-IS": 1,
            "TRANSLATE": 99,
            "CLEAN-ROOM-REIMPLEMENT": 7,
            "REJECT": 3,
        },
        "candidates": candidates,
    }


def mutate_classification(
    candidates: list[dict[str, Any]], cid: str, new_label: str
) -> list[dict[str, Any]]:
    out = []
    for rec in candidates:
        row = dict(rec)
        if row.get("id") == cid:
            row["classification"] = new_label
        out.append(row)
    return out
