"""Selection explanation emitter (IMP-0395)."""
from __future__ import annotations

from typing import Any


def explain_one(trace: dict[str, Any], index: dict[str, Any]) -> dict[str, Any]:
    min_score = float(trace.get("min_score") or 0)
    budget = int(trace.get("budget_tokens") or 10**9)
    margin = float(trace.get("near_miss_margin") or 0.2)
    ov = trace.get("overrides") or {}
    banned = set(ov.get("banned") or [])
    pinned = list(ov.get("pinned") or [])
    cands = list(trace.get("candidates") or [])
    by_id = {c["capability_id"]: c for c in cands}
    selected: list[dict[str, Any]] = []
    spent = 0
    # pinned first
    chosen: set[str] = set()
    for pid in pinned:
        c = by_id.get(pid)
        if not c or pid in banned:
            continue
        selected.append(
            {
                "capability_id": pid,
                "producing_rule": c.get("rule_id") or "PIN",
                "reason": "pinned override",
                "score": c.get("fusion_score"),
            }
        )
        spent += int(c.get("token_cost") or 0)
        chosen.add(pid)
    ranked = sorted(
        [c for c in cands if c["capability_id"] not in banned and c["capability_id"] not in chosen],
        key=lambda c: -float(c.get("fusion_score") or 0),
    )
    for c in ranked:
        score = float(c.get("fusion_score") or 0)
        if score < min_score:
            continue
        cost = int(c.get("token_cost") or 0)
        if spent + cost > budget:
            continue
        selected.append(
            {
                "capability_id": c["capability_id"],
                "producing_rule": c.get("rule_id") or "SCORE",
                "reason": f"fusion_score {score} >= {min_score}",
                "score": score,
            }
        )
        spent += cost
        chosen.add(c["capability_id"])
    near = []
    for c in cands:
        cid = c["capability_id"]
        if cid in chosen or cid in banned:
            continue
        score = float(c.get("fusion_score") or 0)
        if score >= (min_score - margin):
            near.append(
                {
                    "capability_id": cid,
                    "producing_rule": c.get("rule_id") or "NEAR",
                    "reason": "near-miss",
                    "score": score,
                }
            )
    return {
        "query_id": trace.get("query_id"),
        "selected": selected,
        "near_misses": near,
        "budget_tokens": budget,
        "spent": spent,
    }
