"""Probe 1: enumeration + agent-visible rendering versus true byte names.

Mechanically a display/listing measurement. Does not invoke cat/argv/realpath.
"""
from __future__ import annotations

from pathlib import Path

from fixtures import (
    HOMOGLYPH_CONFIG,
    LATIN_CONFIG,
    NEWLINE_NAME,
    ORDINARY,
    RTL_NAME,
    hex_name,
    true_names,
)

RTL_OVERRIDE = "\u202e"
PDF = "\u202c"
CYRILLIC_O = "\u043e"
CYRILLIC_O_CAP = "\u041e"


def visual_render(name: str) -> str:
    """Apply U+202E RTL override for display comparison (not a full UBA)."""
    out: list[str] = []
    i = 0
    n = len(name)
    while i < n:
        ch = name[i]
        if ch == RTL_OVERRIDE:
            chunk: list[str] = []
            i += 1
            while i < n and name[i] != PDF:
                chunk.append(name[i])
                i += 1
            out.extend(reversed(chunk))
            if i < n and name[i] == PDF:
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def confusable_fold(name: str) -> str:
    table = {CYRILLIC_O: "o", CYRILLIC_O_CAP: "O"}
    return "".join(table.get(ch, ch) for ch in name)


def naive_listing(names: list[str]) -> str:
    """Line-oriented prompt listing: join on newline. A newline in a name splits."""
    return "\n".join(sorted(names))


def phantom_lines(listing: str, names: list[str]) -> list[str]:
    true = set(names)
    return [line for line in listing.splitlines() if line not in true]


def read_all(tree: Path, names: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in names:
        out[hex_name(name)] = (tree / name).read_text(encoding="utf-8")
    return out


def probe1_measure(tree: Path) -> dict:
    names = true_names(tree)
    listing = naive_listing(names)
    phantoms = phantom_lines(listing, names)
    rtl_visual = visual_render(RTL_NAME)
    latin_fold = confusable_fold(LATIN_CONFIG)
    twin_fold = confusable_fold(HOMOGLYPH_CONFIG)
    ordinary_visual = visual_render(ORDINARY)
    reads = read_all(tree, names)
    return {
        "probe": "probe1-enumerate-render",
        "true_names": names,
        "true_names_hex": [hex_name(n) for n in names],
        "naive_listing": listing,
        "phantom_lines": phantoms,
        "newline_name_hex": hex_name(NEWLINE_NAME),
        "newline_splits_listing": NEWLINE_NAME not in listing.splitlines()
        and bool(phantoms),
        "rtl_name_hex": hex_name(RTL_NAME),
        "rtl_visual": rtl_visual,
        "rtl_display_diverges": rtl_visual != RTL_NAME,
        "homoglyph_latin": LATIN_CONFIG,
        "homoglyph_twin_hex": hex_name(HOMOGLYPH_CONFIG),
        "homoglyph_nfc_equal": LATIN_CONFIG == HOMOGLYPH_CONFIG,
        "homoglyph_confusable_equal": latin_fold == twin_fold,
        "ordinary": ORDINARY,
        "ordinary_visual": ordinary_visual,
        "ordinary_display_matches_bytes": ordinary_visual == ORDINARY
        and ORDINARY in names,
        "reads_by_hex": reads,
        "ordinary_payload": reads.get(hex_name(ORDINARY), ""),
    }
