#!/usr/bin/env python3
"""Decompose a stage-splice INSERT fusion back to host and donor ids.

WFA-0063 (fusion decomposability) is absent on this worktree. This function
is the per-operator rehearsal: recover source ids from lineage and reconstruct
the host stage list by removing the inserted donor stage. Recovering ids is
weaker than recovering runnable sources; the reconstructed host stages are
compared byte-for-byte against the original host in the probes.
"""
from __future__ import annotations

from typing import Any

from ir import canonical_bytes


def decompose(fusion: dict[str, Any]) -> dict[str, Any]:
    lineage = fusion.get("lineage") or {}
    host_id = lineage.get("host_id")
    donor_id = lineage.get("donor_id")
    insert_index = lineage.get("insert_index")
    stages = list(fusion.get("stages") or [])
    spliced = None
    reconstructed: list[dict[str, Any]] = []
    if isinstance(insert_index, int) and 0 <= insert_index < len(stages):
        spliced = stages[insert_index]
        reconstructed = stages[:insert_index] + stages[insert_index + 1 :]
    else:
        for stage in stages:
            if isinstance(stage, dict) and stage.get("spliced_from"):
                spliced = stage
            elif isinstance(stage, dict):
                reconstructed.append(stage)
    source_ids = []
    for sid in (host_id, donor_id):
        if sid and sid not in source_ids:
            source_ids.append(sid)
    for extra in lineage.get("source_ids") or fusion.get("sources") or []:
        if extra and extra not in source_ids:
            source_ids.append(extra)
    return {
        "ok": bool(host_id and donor_id and spliced is not None),
        "source_ids": source_ids,
        "host_id": host_id,
        "donor_id": donor_id,
        "insert_index": insert_index,
        "spliced_stage_id": (spliced or {}).get("id") if isinstance(spliced, dict) else None,
        "spliced_from": (spliced or {}).get("spliced_from") if isinstance(spliced, dict) else None,
        "reconstructed_host_stage_ids": [
            s.get("id") for s in reconstructed if isinstance(s, dict)
        ],
        "reconstructed_host_stages": reconstructed,
        "reconstructed_count": len(reconstructed),
    }


def host_stages_match(host: dict[str, Any], decomposed: dict[str, Any]) -> dict[str, Any]:
    original = list(host.get("stages") or [])
    rebuilt = list(decomposed.get("reconstructed_host_stages") or [])
    if len(original) != len(rebuilt):
        return {
            "ok": False,
            "reason": "count-mismatch",
            "original_count": len(original),
            "rebuilt_count": len(rebuilt),
        }
    rows = []
    ok = True
    for i, (a, b) in enumerate(zip(original, rebuilt)):
        identical = canonical_bytes(a) == canonical_bytes(b)
        rows.append(
            {
                "index": i,
                "host_stage_id": a.get("id"),
                "identical": identical,
            }
        )
        if not identical:
            ok = False
    return {"ok": ok, "rows": rows}
