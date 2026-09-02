#!/usr/bin/env python3
"""Coverage-gap finder: library categories with ZERO covering candidates."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from taxonomy import Taxonomy, load_spec

HERE = Path(__file__).resolve().parent
DEFAULT_VECTORS = HERE / "fixtures" / "coverage_vectors.json"


@dataclass(frozen=True)
class Candidate:
    id: str
    covers: tuple[str, ...]


def load_vectors(path: Path | None = None) -> list[Candidate]:
    p = path or DEFAULT_VECTORS
    doc = json.loads(p.read_text(encoding="utf-8"))
    out: list[Candidate] = []
    for row in doc.get("candidates") or []:
        covers = tuple(str(x) for x in (row.get("covers") or []))
        out.append(Candidate(id=str(row["id"]), covers=covers))
    return out


def find_gaps(
    taxonomy: Taxonomy, candidates: Iterable[Candidate]
) -> dict:
    """Return categories in taxonomy order that no candidate covers.

    Coverage is a set of category ids (IMP-0177 vector contract), not a
    fixed-width array. Unknown ids are refused rather than silently ignored.
    """
    ids = taxonomy.ids
    idset = set(ids)
    covered: set[str] = set()
    unknown: list[dict] = []
    per_candidate: list[dict] = []
    for cand in candidates:
        bad = [c for c in cand.covers if c not in idset]
        if bad:
            unknown.append({"candidate": cand.id, "unknown_categories": bad})
        hit = [c for c in cand.covers if c in idset]
        covered.update(hit)
        per_candidate.append(
            {
                "id": cand.id,
                "cover_count": len(hit),
                "covers": hit,
            }
        )
    gaps = [cid for cid in ids if cid not in covered]
    family_gaps: dict[str, list[str]] = {}
    for fam in taxonomy.families:
        empty = [leaf for leaf in fam.leaves if leaf not in covered]
        if empty:
            family_gaps[fam.id] = empty
    return {
        "taxonomy_leaf_total": taxonomy.leaf_total,
        "taxonomy_declared_total": taxonomy.declared_total,
        "taxonomy_consistent": not taxonomy.inconsistencies,
        "candidate_count": len(per_candidate),
        "covered_count": len(covered),
        "gap_count": len(gaps),
        "gap_set": gaps,
        "family_gaps": family_gaps,
        "unknown_category_refs": unknown,
        "candidates": per_candidate,
    }


def run(
    spec_path: Path | None = None, vectors_path: Path | None = None
) -> dict:
    tax = load_spec(spec_path)
    vecs = load_vectors(vectors_path)
    result = find_gaps(tax, vecs)
    result["source_spec"] = tax.source_path
    result["families"] = [
        {
            "id": f.id,
            "declared_count": f.declared_count,
            "leaf_count": f.leaf_count,
        }
        for f in tax.families
    ]
    return result


if __name__ == "__main__":
    doc = run()
    print(json.dumps(doc, indent=2))
    if doc["unknown_category_refs"]:
        raise SystemExit(2)
    raise SystemExit(0)
