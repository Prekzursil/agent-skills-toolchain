"""Recommendation logic for CNF-0082.

Found but ranked below a rebuild proposal is a recommendation defect,
not a rediscovery success.
"""
from __future__ import annotations


def assess(hits: list[dict], plant_id: str) -> dict:
    plant = next((h for h in hits if h.get("id") == plant_id), None)
    rebuild = next((h for h in hits if h.get("kind") == "rebuild-proposal"), None)
    if plant is None:
        return {
            "defect": False,
            "plant_rank": None,
            "ranked_above_rebuild": False,
            "rebuild_rank": rebuild.get("rank") if rebuild else None,
            "verdict": "blind",
        }
    plant_rank = int(plant.get("rank") or 0)
    if rebuild is None:
        return {
            "defect": False,
            "plant_rank": plant_rank,
            "ranked_above_rebuild": True,
            "rebuild_rank": None,
            "verdict": "found",
        }
    rebuild_rank = int(rebuild.get("rank") or 0)
    above = plant_rank < rebuild_rank
    if not above:
        return {
            "defect": True,
            "plant_rank": plant_rank,
            "ranked_above_rebuild": False,
            "rebuild_rank": rebuild_rank,
            "verdict": "recommendation-defect",
        }
    return {
        "defect": False,
        "plant_rank": plant_rank,
        "ranked_above_rebuild": True,
        "rebuild_rank": rebuild_rank,
        "verdict": "found",
    }


def ghost_ids(hits: list[dict]) -> list[str]:
    return [str(h.get("id")) for h in hits if str(h.get("id") or "").endswith(".ghost")]
