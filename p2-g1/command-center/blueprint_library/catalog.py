"""Catalog builder: collisions and derived counts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from blueprint_library.fingerprint import fingerprint
from blueprint_library.library import LIBRARY
from blueprint_library.taxonomy import derived_library_total, load_spec_text, parse_category_counts


def build_catalog(root: Path) -> dict[str, Any]:
    spec = load_spec_text(root)
    counts = parse_category_counts(spec)
    fps = [fingerprint(e) for e in LIBRARY]
    collisions = len(fps) - len(set(fps))
    derived = derived_library_total(spec)
    live_counts: dict[str, int] = {}
    for entry in LIBRARY:
        cat = str(entry.get("category") or "unknown")
        live_counts[cat] = live_counts.get(cat, 0) + 1
    return {
        "derived_total": derived,
        "library_len": len(LIBRARY),
        "category_counts": counts,
        "live_category_counts": live_counts,
        "fingerprint_collisions": collisions,
        "counts_agree": derived == len(LIBRARY) and counts == live_counts,
        "unique_fingerprints": len(set(fps)),
    }
