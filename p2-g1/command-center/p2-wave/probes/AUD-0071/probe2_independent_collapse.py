#!/usr/bin/env python3
"""AUD-0071 probe 2 - collapse shared-upstream support, recount, rank.

Mechanically different from probe1: one group-by pass over the edge list
builds target -> distinct supporter sources (the collapse), then re-derives
every ranking score and replays the catalog control cases (five records
citing one upstream score ONE; five independent stay five; no citation
scores zero; a shared-source prose pair creates no edge; the mixed target
scores two) and replays the headline ranking order.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ART = REPO / "command-center" / "audit" / "AUD-0071-support-edge-graph.json"
UNIT = "AUD-0071"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in (doc.get("nodes") or [])}
    edges = doc.get("support_edges") or []
    per_claim = {r.get("claim_id"): r for r in (doc.get("per_claim") or [])}
    if not nodes or not per_claim:
        return fail("graph empty")

    raw: defaultdict[str, int] = defaultdict(int)
    indep: defaultdict[str, set] = defaultdict(set)
    for e in edges:
        raw[e["to"]] += 1
        indep[e["to"]].add(e["supporter_source_id"])

    checks = [
        ("CTL-FIVE-ONE-TARGET", 5, 1),
        ("CTL-FIVE-INDEP-TARGET", 5, 5),
        ("CTL-NOCITE", 0, 0),
    ]
    for cid, want_raw, want_ind in checks:
        if cid not in nodes:
            return fail(f"control node missing: {cid}")
        if raw[cid] != want_raw or len(indep[cid]) != want_ind:
            return fail(
                f"control {cid}: recount raw={raw[cid]} indep={len(indep[cid])} "
                f"want raw={want_raw} indep={want_ind}"
            )
        rec = per_claim[cid]
        if rec.get("raw_support_count") != want_raw or rec.get("independent_source_count") != want_ind:
            return fail(f"control {cid}: per_claim disagrees with recount")
    print("controls five-records-one-upstream=1 five-independent=5 nocite=0 recomputed from edges")

    mixed = per_claim.get("CTL-MIXED-TARGET")
    if not mixed or mixed.get("independent_source_count") != 2:
        return fail("control CTL-MIXED-TARGET: independent count != 2")
    a, b = nodes.get("CTL-PROSE-A"), nodes.get("CTL-PROSE-B")
    if not a or not b:
        return fail("control prose pair missing")
    if a.get("source_id") != b.get("source_id"):
        return fail("prose pair expected to share one upstream source")
    between = [e for e in edges if {e.get("from"), e.get("to")} == {"CTL-PROSE-A", "CTL-PROSE-B"}]
    if between:
        return fail("prose mention produced an edge (must not)")
    print("controls mixed=2 prose-pair-no-edge recomputed")

    bad = []
    for cid, rec in per_claim.items():
        want = len(indep.get(cid, set()))
        if rec.get("ranking_score") != want or rec.get("independent_source_count") != want:
            bad.append(f"{cid}: artifact={rec.get('ranking_score')} recount={want}")
    if bad:
        for m in bad[:8]:
            print(f"  RANK-MISMATCH {m}")
        return fail(f"ranking scores mismatched on {len(bad)} claim(s)")

    hl = doc.get("headline") or {}
    ranked = hl.get("ranked_by_independent_source_count") or []
    order = sorted(
        per_claim.values(),
        key=lambda r: (-int(r["ranking_score"]), str(r["claim_id"])),
    )
    live_top = [r["claim_id"] for r in order[: len(ranked)]]
    if live_top != [x.get("claim_id") for x in ranked]:
        return fail(
            f"headline ranking order drifted: live={live_top} "
            f"artifact={[x.get('claim_id') for x in ranked]}"
        )
    for row, want in zip(order[: len(ranked)], ranked):
        if row["ranking_score"] != want.get("independent_source_count"):
            return fail(f"headline {row['claim_id']} score disagrees")
    print(f"ranking verified for {len(per_claim)} claims; headline top-{len(ranked)} order exact")
    print(f"SUCCESS:{UNIT}-probe2 independent-source collapse and ranking")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
