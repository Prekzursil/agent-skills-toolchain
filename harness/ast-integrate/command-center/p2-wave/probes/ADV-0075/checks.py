"""Shared detectors: ordinary-name identity and both-states planted defects."""
from __future__ import annotations

import json

from rendering import confusable_fold, naive_listing, phantom_lines, visual_render


def ordinary_identity(
    p1_name: str, p2_name: str, expected: str = "ordinary.txt"
) -> bool:
    return p1_name == p2_name == expected


ordinary_identity = ordinary_identity


def control_display_matches(name: str, displayed: str) -> bool:
    return name == displayed


def planted_control_display_fires(name: str) -> bool:
    """Planted defect: display renderer appends a suffix. Detector must fire."""
    fake = name + ".forged"
    return not control_display_matches(name, fake)


def listing_phantoms_on_naive_not_on_json(names: list[str]) -> dict:
    naive = phantom_lines(naive_listing(names), names)
    recovered = json.loads(json.dumps(sorted(names)))
    json_phantoms = [n for n in recovered if n not in set(names)]
    return {
        "naive_phantoms": naive,
        "json_phantoms": json_phantoms,
        "naive_fires": bool(naive),
        "json_silent": json_phantoms == [] and recovered == sorted(names),
    }


def planted_rtl_on_ordinary(name: str = "ordinary.txt") -> bool:
    """If U+202E is injected into an ordinary name, visual_render must diverge."""
    forged = "ord" + "\u202e" + "txt.inary"
    return visual_render(forged) != forged and name == "ordinary.txt"


def planted_homoglyph_fold_equal() -> bool:
    return confusable_fold("config.json") == confusable_fold("c\u043enfig.json")
