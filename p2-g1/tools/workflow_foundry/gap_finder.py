"""Parse the required-library taxonomy from spec text (IMP-0194). Size is parsed, never hardcoded."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_SPEC = HERE / "taxonomy" / "required-library.spec.md"


@dataclass
class Taxonomy:
    source_path: str
    leaves: list[str]
    by_family: dict[str, list[str]]
    size: int


def parse_taxonomy(text: str, source_path: str = "") -> Taxonomy:
    family = "default"
    by_family: dict[str, list[str]] = {}
    leaves: list[str] = []
    for raw in text.splitlines():
        ln = raw.strip()
        if ln.lower().startswith("## family:"):
            family = ln.split(":", 1)[1].strip()
            by_family.setdefault(family, [])
            continue
        if ln.startswith("- "):
            leaf = ln[2:].strip()
            leaves.append(leaf)
            by_family.setdefault(family, []).append(leaf)
    return Taxonomy(
        source_path=source_path,
        leaves=leaves,
        by_family=by_family,
        size=len(leaves),
    )


def load_taxonomy(path: str | Path | None = None) -> Taxonomy:
    loc = Path(path) if path else DEFAULT_SPEC
    return parse_taxonomy(loc.read_text(encoding="utf-8"), source_path=str(loc))


def covering_stubs(tax: Taxonomy, omit: list[str] | None = None) -> list[dict[str, Any]]:
    skip = set(omit or [])
    out = []
    for leaf in tax.leaves:
        if leaf in skip:
            continue
        out.append({"id": f"stub-{leaf}", "covers": [leaf], "category": leaf.split(":")[0]})
    return out


def find_gaps(tax: Taxonomy, library: list[dict[str, Any]]) -> dict[str, Any]:
    covered: set[str] = set()
    for item in library:
        cat = item.get("category")
        # A cover is TYPED: it counts only when the item's category matches the
        # leaf's family (segment before ':'). Category-only never covers a
        # specific leaf, and an untyped/wrong-category cover leaves the gap.
        for c in item.get("covers") or []:
            leaf = str(c)
            family = leaf.split(":", 1)[0].strip() if ":" in leaf else leaf
            if cat is not None and str(cat).strip() == family:
                covered.add(leaf)
    gaps = [leaf for leaf in tax.leaves if leaf not in covered]
    return {"gaps": gaps, "gap_count": len(gaps), "covered": sorted(covered)}
