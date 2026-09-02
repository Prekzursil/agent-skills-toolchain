"""Independent spot-check: read blueprint bodies, not the incidence matrix."""
from __future__ import annotations

from typing import Any

from extract import extract_from_definition, vocab_ids


def _spot_limit(uncovered: list[str], empty: list[str], n: int = 10) -> list[tuple[str, str]]:
    """Prefer mixing both directions. Never take only uncovered mechanisms."""
    pairs: list[tuple[str, str]] = []
    ui, ei = 0, 0
    while len(pairs) < n and (ui < len(uncovered) or ei < len(empty)):
        if ui < len(uncovered):
            pairs.append(("uncovered_mechanism", uncovered[ui]))
            ui += 1
        if len(pairs) >= n:
            break
        if ei < len(empty):
            pairs.append(("empty_blueprint", empty[ei]))
            ei += 1
    return pairs


def spot_check(
    *,
    uncovered: list[str],
    empty_blueprints: list[str],
    blueprints: list[dict[str, Any]],
    kind_map: dict[str, str],
    vocabulary: list[dict[str, Any]],
    n: int = 10,
) -> dict[str, Any]:
    vids = vocab_ids(vocabulary)
    by_id = {str(b["id"]): b for b in blueprints if isinstance(b, dict) and b.get("id")}
    claimed = _spot_limit(uncovered, empty_blueprints, n)
    rows: list[dict[str, Any]] = []
    rerun_needed = False
    for direction, gap_id in claimed:
        if direction == "uncovered_mechanism":
            hits: list[str] = []
            for bid, body in by_id.items():
                mechs = extract_from_definition(body, kind_map, vids)
                if gap_id in mechs:
                    hits.append(bid)
            survived = len(hits) == 0
            if not survived:
                rerun_needed = True
            rows.append(
                {
                    "gap_id": gap_id,
                    "direction": direction,
                    "method": "read-blueprint-bodies",
                    "blueprints_read": sorted(by_id),
                    "implements_found": hits,
                    "survived": survived,
                    "extraction_rerun": not survived,
                }
            )
        else:
            body = by_id.get(gap_id)
            if body is None:
                rerun_needed = True
                rows.append(
                    {
                        "gap_id": gap_id,
                        "direction": direction,
                        "method": "read-blueprint-body",
                        "body_mechanisms": [],
                        "survived": False,
                        "extraction_rerun": True,
                        "error": "blueprint-body-missing",
                    }
                )
                continue
            mechs = extract_from_definition(body, kind_map, vids)
            survived = len(mechs) == 0
            if not survived:
                rerun_needed = True
            rows.append(
                {
                    "gap_id": gap_id,
                    "direction": direction,
                    "method": "read-blueprint-body",
                    "body_mechanisms": mechs,
                    "survived": survived,
                    "extraction_rerun": not survived,
                }
            )
    n_survived = sum(1 for r in rows if r.get("survived") is True)
    directions = {r["direction"] for r in rows}
    return {
        "n_requested": n,
        "n_checked": len(rows),
        "n_survived": n_survived,
        "all_survived": bool(rows) and n_survived == len(rows),
        "both_directions_in_sample": "uncovered_mechanism" in directions
        and "empty_blueprint" in directions,
        "extraction_rerun_needed": rerun_needed,
        "rows": rows,
    }
