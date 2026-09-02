"""Carry predicates for provenance_anchor and licence_class.

Empty string is lost, identically to a missing key (WFA-0122 tests_required).
Whitespace-only is also lost: a naive `if not value` check treats '  ' as
present, which is the named bypass this unit closes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

HOPS = (
    "acquisition",
    "extraction",
    "translation",
    "dedup collapse",
    "fusion",
    "certification",
)

ANCHOR_KEY = "provenance_anchor"
LICENCE_KEY = "licence_class"

# Most-restrictive-wins lattice. Higher rank is stricter. UNCLASSIFIED is a
# present honest token (WFA-0079: never default a fetch failure to a licence).
LICENCE_RANK = {
    "UNCLASSIFIED": 0,
    "MIT": 1,
    "Apache-2.0": 2,
    "CC-BY-4.0": 3,
    "GPL-3.0": 4,
}


def load_seed(name: str) -> dict[str, Any]:
    path = HERE / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


SEED_A = load_seed("seed-a.json")
SEED_B = load_seed("seed-b.json")


def is_lost(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return True
    return value.strip() == ""


def field_lost(artifact: dict[str, Any], key: str) -> bool:
    if key not in artifact:
        return True
    return is_lost(artifact.get(key))


def stricter_licence(a: str, b: str) -> str:
    ra = LICENCE_RANK.get(a, -1)
    rb = LICENCE_RANK.get(b, -1)
    if ra < 0 or rb < 0:
        raise ValueError(f"unknown licence class in lattice: {a!r} {b!r}")
    return a if ra >= rb else b


def gate_id_for(hop: str) -> str:
    return "WFA-0122-gate-" + hop.replace(" ", "-")
