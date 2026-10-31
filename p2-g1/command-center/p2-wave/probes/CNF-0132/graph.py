"""CNF-0132 independence graph: union-find over shared upstream inputs.

Rule 5 of rules/common/single-signal-verification.md: N confirmations that all
read ONE upstream artifact are ONE signal regardless of how many agents
produced them. rank(claim) = number of disjoint upstream components among the
claim's sourced CONFIRMED records. Rebuilt 2026-10-26 (wave-3 shard 5).
Rebuilt 2026-10-26 (wave-3 shard 7) after the original probe tree was lost;
the algorithm contract is pinned by the published edge_list and per-claim
ranks in command-center/receipts/CNF-0132.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_frame(path: Path) -> dict[str, "Any"]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_edges(frame: dict[str, Any]) -> list[dict[str, str]]:
    """Emit the directed edge list: confirmation -> probe -> upstream node."""
    edges: list[dict[str, str]] = []
    for rec in frame["records"]:
        for role in ("source_probe", "verifier_probe"):
            pid = rec.get(role)
            if not pid:
                continue
            edges.append(
                {
                    "from": f"confirmation:{rec['record_id']}",
                    "kind": "uses-probe",
                    "to": "probe:" + pid,
                    "via": role,
                }
            )
            for ups in frame.get("probe_upstreams", {}).get(pid, []):
                edges.append(
                    {
                        "from": "probe:" + pid,
                        "kind": "reads",
                        "to": "upstream:" + ups,
                        "via": role,
                    }
                )
    return edges


class UF:
    """Minimal union-find with path halving."""

    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        self.parent.setdefault(x, x)

    def find(self, x: str) -> str:
        self.add(x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def ups_of_record(frame: dict[str, list[str]], rec: dict) -> set:
    return set(frame.get("probe_upstreams", {}).get(rec.get("source_probe"), [])) | set(
        frame.get("probe_upstreams", {}).get(rec.get("verifier_probe"), [])
    )


def build(frame: dict[str, Any]) -> dict[str, Any]:
    """Union-find over shared upstreams; per-claim rank + collapse report."""
    records = frame["records"]
    ups_of = {r["record_id"]: ups_of_record(frame, r) for r in records}
    per_claim_records: dict[str, list] = {}
    for r in records:
        per_claim_records.setdefault(r["claim_id"], []).append(r)

    per_claim: dict[str, Any] = {}
    for claim_id in sorted(per_claim_records):
        recs = per_claim_records[claim_id]
        sourced = [r for r in recs if r.get("verdict") == "CONFIRMED" and ups_of[r["record_id"]]]
        uf = UF()
        # node = upstream id; each record joins the component of each upstream it reads
        for r in sourced:
            for u in ups_of[r["record_id"]]:
                uf.add(u)
                uf.union(u, "rec:" + r["record_id"])
        comps: dict[str, list] = {}
        for r in sourced:
            comps.setdefault(uf.find("rec:" + r["record_id"]), []).append(r["record_id"])
        independent_sets = []
        for root in sorted(comps):
            members = sorted(comps[root])
            if len(members) > 1:
                shared = set(ups_of[members[0]])
                for m in members[1:]:
                    shared &= set(ups_of[m])
            else:
                shared = set()
            independent_sets.append(
                {
                    "component_id": claim_id + ":" + members[0],
                    "record_ids": members,
                    "shared_upstreams": sorted(shared),
                    "upstreams": sorted(set().union(*(set(ups_of[m]) for m in members))),
                }
            )
        rank = len(independent_sets)
        apparent_n = len(sourced)
        per_claim[claim_id] = {
            "claim_id": claim_id,
            "total_records": len(recs),
            "sourced_confirmed": apparent_n,
            "apparent_n": apparent_n,
            "rank": rank,
            "collapsed": rank < apparent_n,
            "independent_sets": independent_sets,
        }
    rank_distribution: dict = {}
    for c in per_claim.values():
        key = str(c["rank"])
        rank_distribution[key] = rank_distribution.get(key, 0) + 1
    distribution = {k: rank_distribution[k] for k in sorted(rank_distribution)}
    return {
        "per_claim": per_claim,
        "rank_distribution": distribution,
        "assigned_records": sum(c["total_records"] for c in per_claim.values()),
        "total_records": len(records),
        "unique_records": len(set(r["record_id"] for r in records)),
        "edges": build_edges(frame),
    }


def components_by_dfs(ups_of: dict, sourced_ids: list) -> int:
    """Mechanically different lane: connected components via record overlap BFS.

    Two records share a component iff their upstream sets intersect. No
    union-find involved - used by probe2 to cross-check graph.build.
    """
    remaining = list(sourced_ids)
    count = 0
    while remaining:
        count += 1
        seed = remaining.pop(0)
        comp = [seed]
        changed = True
        while changed:
            changed = False
            seed_ups = set(ups_of[seed])
            for other in list(remaining):
                if seed_ups & set(ups_of[other]):
                    remaining.remove(other)
                    comp.append(other)
                    seed_ups |= set(ups_of[other])
                    changed = True
    return count


def rank1_collapse_report(build_result: dict, claim_id: str) -> dict:
    """Cite the shared upstream node for every rank-1 collapse."""
    c = build_result["per_claim"][claim_id]
    shared_nodes = []
    for s in c["independent_sets"]:
        for u in s["shared_upstreams"]:
            shared_nodes.append("upstream:" + u)
    return {
        "apparent_n": c["apparent_n"],
        "claim_id": claim_id,
        "independent_sets": c["independent_sets"],
        "rank": c["rank"],
        "shared_upstream_nodes": shared_nodes,
        "shared_upstreams": sorted(
            {u for s in c["independent_sets"] for u in s["shared_upstreams"]}
        ),
    }
