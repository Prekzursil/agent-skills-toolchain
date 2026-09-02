"""English-language deliberation/orchestration corpus for RES-0116.

The program's named protocol inventory is the reconstructed 58-protocol
list in CNL-0102 (the original 12-COUNCIL library file is absent). Extra
terms are taken from tools/council module names. This is the English
corpus against which non-English mechanisms are compared.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CNL = REPO / "command-center" / "p2-wave" / "probes" / "CNL-0102"

sys.path.insert(0, str(CNL))
from catalog import PROTOCOLS  # noqa: E402

ABSENCE_NEEDLES = (
    "ringi",
    "稟議",
    "りんぎ",
    "nemawashi",
    "根回し",
    "ねまわし",
    "품의",
    "기안자",
    "위임전결",
    "合议庭",
    "合議庭",
    "少数服从多数",
    "kollegialprinzip",
    "kollegialorgan",
    "коллегиальность",
    "коллегиальный",
)


def protocol_inventory() -> list[dict]:
    return [
        {"id": pid, "family": family, "slug": slug}
        for pid, family, slug in PROTOCOLS
    ]


def slug_set() -> set[str]:
    return {slug.lower() for _pid, _fam, slug in PROTOCOLS}


def council_module_text() -> str:
    root = REPO / "tools" / "council"
    if not root.is_dir():
        return ""
    parts: list[str] = []
    for path in sorted(root.rglob("*.py")):
        parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def absence_scan() -> dict:
    slugs = slug_set()
    joined_slugs = " ".join(sorted(slugs))
    council = council_module_text().lower()
    hits = []
    for needle in ABSENCE_NEEDLES:
        in_slug = needle.lower() in joined_slugs
        in_code = needle.lower() in council
        if in_slug or in_code:
            hits.append(
                {"needle": needle, "in_protocol_slugs": in_slug, "in_council_code": in_code}
            )
    return {
        "protocol_count": len(PROTOCOLS),
        "needles": list(ABSENCE_NEEDLES),
        "hits": hits,
        "absent": len(hits) == 0,
    }
