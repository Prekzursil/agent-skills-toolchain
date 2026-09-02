#!/usr/bin/env python3
"""Planted control: one reworded duplicate and one distinct near-neighbour."""
from __future__ import annotations

from typing import Any


SEED_ID = "ADV-0114-PLANT-SEED"
REWORD_ID = "ADV-0114-PLANT-REWORD"
NEIGHBOUR_ID = "ADV-0114-PLANT-NEIGHBOUR"
SYN_MECH = "python-pep440:planted-pkg:range:floats"
SYN_FIX = "pin-exclusive-upper-bound:planted-pkg:gte68"
SYN_TEXT = (
    "The planted-pkg constraint '>=68' is a floating range that admits "
    "new majors with no exclusive upper bound."
)


def synthetic_seed() -> dict[str, Any]:
    return {
        "id": SEED_ID,
        "native_id": SEED_ID,
        "source_path": "command-center/p2-wave/probes/ADV-0114/control_planted.py",
        "source_loc": "synthetic",
        "text": SYN_TEXT,
        "mechanism_key": SYN_MECH,
        "fix_key": SYN_FIX,
        "files": [],
        "plant": "seed",
        "live": False,
        "canonical_mechanism_declared": True,
    }


def reword_text(text: str) -> str:
    swapped = (
        text.replace("declared", "specified")
        .replace("floating", "unbounded")
        .replace("fails", "does not pass")
    )
    return (
        "Reworded duplicate (wording, scope or affected file only): "
        + swapped
        + " Synonym restatement of the same mechanism and the same fix."
    )


def neighbour_text(text: str) -> str:
    return (
        "Genuinely distinct near-neighbour (similar wording, different "
        "object): "
        + text
        + " This row is about planted-neighbour-pkg, not the seed object, "
        "and the required change is a different pin."
    )


def overlay_plants(live: list[dict]) -> tuple[list[dict], str]:
    """Return (planted rows, seed id used for collapse checks)."""
    plants: list[dict] = []
    if live:
        seed = live[0]
        seed_id = seed["id"]
        base_text = seed["text"]
        mech = seed["mechanism_key"]
        fix = seed["fix_key"]
        source = seed["source_path"]
    else:
        seed = synthetic_seed()
        plants.append(seed)
        seed_id = seed["id"]
        base_text = seed["text"]
        mech = seed["mechanism_key"]
        fix = seed["fix_key"]
        source = seed["source_path"]
    plants.append(
        {
            "id": REWORD_ID,
            "native_id": REWORD_ID,
            "source_path": source,
            "source_loc": "planted-control",
            "text": reword_text(base_text),
            "mechanism_key": mech,
            "fix_key": fix,
            "files": [],
            "plant": "reword",
            "live": False,
            "canonical_mechanism_declared": True,
        }
    )
    plants.append(
        {
            "id": NEIGHBOUR_ID,
            "native_id": NEIGHBOUR_ID,
            "source_path": source,
            "source_loc": "planted-control",
            "text": neighbour_text(base_text),
            "mechanism_key": slug_distinct(mech),
            "fix_key": slug_distinct(fix),
            "files": [],
            "plant": "neighbour",
            "live": False,
            "canonical_mechanism_declared": True,
        }
    )
    return plants, seed_id


def slug_distinct(key: str) -> str:
    return f"{key}-near-neighbour-distinct"
