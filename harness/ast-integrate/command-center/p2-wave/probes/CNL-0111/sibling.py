"""Nearest-sibling differential against the CNL-0102 reconstructed library.

Original 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is ABSENT. Sibling search uses
the catalog-cited reconstruction in probes/CNL-0102/catalog.py. This unit OWNS
C15 and C16, so self-ids are excluded; otherwise the nearest sibling of C15
would be C15 at distance 0 (a tautology, not a proof).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CNL0102 = HERE.parent / "CNL-0102"


def _load_distinctness():
    sys.path.insert(0, str(CNL0102))
    import catalog as C  # noqa: E402
    import distinctness as D  # noqa: E402

    return C, D


def library_presets() -> tuple[list[dict], dict[str, Any]]:
    C, D = _load_distinctness()
    corpus = C.load_corpus()
    return list(corpus["presets"]), {
        "source": corpus["source"],
        "original_library_present": corpus["original_library_present"],
        "preset_count": corpus["preset_count"],
        "distinctness_module": str(CNL0102 / "distinctness.py"),
        "distance": D.distance,
        "threshold": D.THRESHOLD,
    }


def nearest_sibling(
    probe: dict, library: list[dict], *, exclude_ids: set[str]
) -> dict[str, Any]:
    C, D = _load_distinctness()
    best: dict[str, Any] | None = None
    for other in library:
        oid = other["id"]
        if oid in exclude_ids:
            continue
        d = D.distance(probe, other)
        cand = {
            "id": probe["id"],
            "neighbour_id": oid,
            "neighbour_name": other.get("name"),
            "distance": d,
            "same_signature": d <= D.THRESHOLD,
            "neighbour_vote": other.get("voting_method"),
            "neighbour_stop": other.get("stopping_expression"),
            "neighbour_protocols": list(other.get("bound_protocols") or []),
            "neighbour_roles": list(other.get("roles") or []),
        }
        if best is None:
            best = cand
            continue
        if d < best["distance"] or (
            d == best["distance"] and oid < best["neighbour_id"]
        ):
            best = cand
    if best is None:
        raise RuntimeError("library empty after exclude")
    return best


def pairwise_distance(a: dict, b: dict) -> float:
    _, D = _load_distinctness()
    return D.distance(a, b)


def plant_renamed_duplicate(src: dict, new_id: str) -> dict:
    clone = dict(src)
    clone["id"] = new_id
    clone["name"] = str(src.get("name") or "preset") + "-renamed-id"
    return clone
