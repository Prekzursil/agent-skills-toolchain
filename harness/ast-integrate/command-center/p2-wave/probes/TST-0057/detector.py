"""NFC/NFD collision detector with a planted-NFD control.

Zero live non-ASCII ids is acceptable only if this detector finds the
planted pair. The plant is generated in memory (Å U+00C5 vs A + U+030A)
so an editor or filesystem cannot NFC-collapse the fixture file.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools" / "command-center"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import id_normalize as inn  # noqa: E402

# LATIN CAPITAL LETTER A WITH RING ABOVE vs A + COMBINING RING ABOVE.
PLANTED_NFC = "PLANT-\u00c5-0057"
PLANTED_NFD = inn.nfd_form(PLANTED_NFC)


def planted_pair() -> dict[str, str]:
    if PLANTED_NFC == PLANTED_NFD:
        raise RuntimeError("planted NFC/NFD pair collapsed; detector is vacuous")
    if inn.canonical_id(PLANTED_NFD) != PLANTED_NFC:
        raise RuntimeError("planted NFD does not NFC-fold to planted NFC")
    if inn.byte_key(PLANTED_NFC) == inn.byte_key(PLANTED_NFD):
        raise RuntimeError("planted pair is not byte-distinct")
    return {
        "nfc": PLANTED_NFC,
        "nfd": PLANTED_NFD,
        "nfc_utf8_hex": inn.byte_key(PLANTED_NFC).hex(),
        "nfd_utf8_hex": inn.byte_key(PLANTED_NFD).hex(),
        "canonical_form": inn.CANONICAL_FORM,
    }


def detect(ids: Iterable[str]) -> list[dict[str, Any]]:
    return inn.collision_groups(ids)


def detect_planted() -> dict[str, Any]:
    pair = planted_pair()
    groups = detect([pair["nfc"], pair["nfd"], "TST-0057", "PLANT-OTHER-0057"])
    hit = None
    for group in groups:
        forms = set(group["forms"])
        if pair["nfc"] in forms and pair["nfd"] in forms:
            hit = group
            break
    ascii_false = [g for g in groups if "TST-0057" in g["forms"]]
    return {
        "pair": pair,
        "groups": groups,
        "planted_hit": hit is not None,
        "planted_group": hit,
        "ascii_id_not_colliding": not ascii_false,
        "group_count": len(groups),
    }
