#!/usr/bin/env python3
"""Second independent signal: expand top-k ids into an executed tool sequence.

The executor reads only the structured `tools` field on each selected
capability. It never reads description / SKILL.md. Injection into prose
can change this sequence only by first changing top-k.
"""
from __future__ import annotations


def execute(top_k: list[str], catalog: list[dict]) -> list[str]:
    by_id = {str(c["id"]): c for c in catalog}
    seq: list[str] = []
    for cid in top_k:
        cap = by_id.get(cid)
        if cap is None:
            seq.append(f"MISSING:{cid}")
            continue
        tools = cap.get("tools") or []
        seq.extend(str(t) for t in tools if isinstance(t, str))
    return seq
