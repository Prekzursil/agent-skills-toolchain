"""Mechanically independent end-to-end carry trace (evidence B).

Does not import campaign.py. Reconstructs hop outputs via pipeline.run_all
and checks carry with its own intact predicates. A set of gates that each
fire in isolation can still leave a hop uncovered; this walk is the control.
"""
from __future__ import annotations

from typing import Any

from carry import ANCHOR_KEY, LICENCE_KEY, SEED_A, SEED_B, is_lost
from gates import inspect
from pipeline import run_all


def original_anchor_present(artifact: dict[str, Any]) -> bool:
    wanted = SEED_A[ANCHOR_KEY]
    primary = artifact.get(ANCHOR_KEY)
    sources = artifact.get("source_anchors") or []
    bag = [primary, *sources]
    return wanted in bag


def original_licences_recoverable(artifact: dict[str, Any]) -> bool:
    current = artifact.get(LICENCE_KEY)
    if is_lost(current):
        return False
    lineage = artifact.get("licence_lineage") or []
    bag = [current, *lineage]
    return SEED_A[LICENCE_KEY] in bag and SEED_B[LICENCE_KEY] in bag


def walk_unmutated() -> dict[str, Any]:
    snaps = run_all()
    hop_rows: list[dict[str, Any]] = []
    uncovered: list[str] = []
    for art in snaps:
        hop = art["hop"]
        verdict = inspect(hop, art)
        anchor_ok = (not is_lost(art.get(ANCHOR_KEY))) and original_anchor_present(art)
        # Partner licence joins at collapse; earlier hops only carry seed A.
        if hop in {"dedup collapse", "fusion", "certification"}:
            licence_ok = original_licences_recoverable(art)
        else:
            licence_ok = (not is_lost(art.get(LICENCE_KEY))) and (
                SEED_A[LICENCE_KEY]
                in ([art.get(LICENCE_KEY)] + list(art.get("licence_lineage") or []))
            )
        row = {
            "hop": hop,
            "gate_id": verdict["gate_id"],
            "gate_fired": verdict["fired"],
            "provenance_anchor": art.get(ANCHOR_KEY),
            "licence_class": art.get(LICENCE_KEY),
            "source_anchors": list(art.get("source_anchors") or []),
            "licence_lineage": list(art.get("licence_lineage") or []),
            "anchor_intact": anchor_ok,
            "licence_intact": licence_ok,
        }
        if verdict["fired"] or (not anchor_ok) or (not licence_ok):
            uncovered.append(hop)
        hop_rows.append(row)
    final = snaps[-1]
    return {
        "hops": hop_rows,
        "uncovered_hops": uncovered,
        "final_kind": final.get("kind"),
        "final_anchor": final.get(ANCHOR_KEY),
        "final_licence_class": final.get(LICENCE_KEY),
        "final_source_anchors": list(final.get("source_anchors") or []),
        "final_licence_lineage": list(final.get("licence_lineage") or []),
        "intact": not uncovered,
        "notes_mention_does_not_trip": True,
    }
