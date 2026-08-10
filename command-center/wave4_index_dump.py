#!/usr/bin/env python
"""Scratch: dump index shape + a stride sample so QS-C gold labels can be authored
against records that EXIST and are DISJOINT from the lane's own gold sets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent.parent / "platform"
sys.path.insert(0, str(BUILD))

from routing import index as ridx  # noqa: E402
from routing import queries as rq  # noqa: E402

idx = ridx.discover()
qs = rq.build(idx)

lane_gold: set[str] = set()
for q in qs.queries:
    lane_gold |= set(q.gold)
    if q.holdout_id:
        lane_gold.add(q.holdout_id)

print(
    json.dumps(
        {
            "total": len(idx.records),
            "counts": dict(sorted(idx.counts.items())),
            "lane_query_count": len(qs.queries),
            "lane_tiers": qs.counts(),
            "lane_gold_or_holdout_ids": sorted(lane_gold),
        },
        indent=1,
    )
)

print("\n==== STRIDE SAMPLE (disjoint from lane gold) ====")
want = {
    "skill",
    "workflow",
    "protocol",
    "agent",
    "command",
    "mcp",
    "preset",
    "candidate",
    "plugin",
}
shown = 0
for i, r in enumerate(idx.records):
    if r.cls not in want or r.id in lane_gold:
        continue
    if i % 23:
        continue
    d = (r.desc_source or "")[:230].replace("\n", " ")
    print(f"[{i:4d}] {r.id}  ||  {d}")
    shown += 1
    if shown >= 70:
        break
