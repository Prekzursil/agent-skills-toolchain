#!/usr/bin/env python3
"""Independence graph for confirmation records (CNF-0132).

Rule (single-signal-verification rule 5): two confirmations that share one
upstream input are ONE signal, regardless of how many agents produced them.

Directed graph, recomputable from the emitted edge list:

    confirmation --uses-probe--> probe --reads--> upstream

Independence rank of a claim = number of connected components among CONFIRMED
confirmations in the UNDIRECTED graph whose edges mean 'share at least one
reachable upstream'. Union-find over confirmations, unioned when upstream
sets intersect.

Agent identity and vendor are never upstream nodes. Shell, tool, and field
are probe mechanics, not inputs: they do not collapse two chains unless those
chains also share an explicit upstream (cached artifact, file, sha256, URL).

An empty source_probe on a CONFIRMED record contributes rank 0 (undeclared
source is zero signals, not one). This unit does not plant that invalid
shape; CNF-0129 makes it structurally invalid.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any, Iterable


CONFIRMED = "CONFIRMED"
PROBE_KEYS = (
    "source_probe",
    "verifier_probe",
    "source_probe",
    "verifier_probe",
)
UPSTREAM_KEYS = (
    "upstream",
    "upstreams",
    "cached_artifact",
    "cached_artifacts",
    "artifact",
    "artifacts",
    "input",
    "inputs",
    "source",
    "sources",
    "source_lineage",
    "lineage",
)


class UnionFind:
    """Disjoint-set with path compression and union by rank."""

    def __init__(self) -> None:
        self.parent: dict[str, str] = {}
        self.sz: dict[str, int] = {}

    def add(self, x: str) -> None:
        if x not in self.parent:
            self.parent[x] = x
            self.sz[x] = 0

    def find(self, x: str) -> str:
        self.add(x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.sz[ra] < self.sz[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.sz[ra] == self.sz[rb]:
            self.sz[ra] += 1

    def components(self, members: Iterable[str]) -> dict[str, list[str]]:
        out: dict[str, list[str]] = defaultdict(list)
        for m in members:
            out[self.find(m)].append(m)
        return {k: sorted(v) for k, v in out.items()}


def _as_ids(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        ids: list[str] = []
        for key in (
            "id",
            "uri",
            "url",
            "path",
            "sha256",
            "hash",
            "artifact",
            "cache",
            "fingerprint",
        ):
            val = value.get(key)
            if not val:
                continue
            if key == "sha256":
                ids.append(f"sha256:{val}")
            else:
                ids.append(str(val))
        nested = value.get("upstream") or value.get("upstreams")
        if nested:
            ids.extend(_as_ids(nested))
        return ids
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            out.extend(_as_ids(item))
        return out
    return [str(value)]


def probe_fingerprint(probe: Any) -> str:
    if probe is None or probe == "":
        return ""
    if isinstance(probe, str):
        return hashlib.sha256(probe.encode("utf-8")).hexdigest()
    if not isinstance(probe, dict):
        return hashlib.sha256(str(probe).encode("utf-8")).hexdigest()
    payload = {
        "command": probe.get("command"),
        "engine": probe.get("engine"),
        "field": probe.get("field"),
        "shell": probe.get("shell"),
        "tool": probe.get("tool"),
        "upstream": probe.get("upstream")
        or probe.get("upstreams")
        or probe.get("cached_artifact")
        or probe.get("artifact"),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def extract_upstreams(probe: Any) -> list[str]:
    """Return explicit upstream input ids. Shell/tool/field are not inputs."""
    if probe is None or probe == "" or probe == {}:
        return []
    if isinstance(probe, str):
        return [f"probe-fp:{probe}"]
    if not isinstance(probe, dict):
        return [f"probe-fp:{probe}"]
    ids: list[str] = []
    for key in UPSTREAM_KEYS:
        if key in probe:
            ids.extend(_as_ids(probe.get(key)))
    if not ids:
        fp = probe.get("fingerprint") or probe_fingerprint(probe)
        if fp:
            ids.append(f"probe-fp:{fp}")
    seen: set[str] = set()
    out: list[str] = []
    for item in ids:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def probes_of(record: dict) -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []
    seen_keys: set[str] = set()
    for key in PROBE_KEYS:
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if key in record:
            found.append((key, record[key]))
    extra = record.get("probes")
    if isinstance(extra, list):
        for i, probe in enumerate(extra):
            found.append((f"probes[{i}]", probe))
    return found


def record_id_of(record: dict, fallback: str) -> str:
    for key in ("record_id", "id", "confirmation_id"):
        val = record.get(key)
        if val:
            return str(val)
    return fallback


def claim_id_of(record: dict) -> str:
    for key in ("claim_id", "claim", "target_claim"):
        val = record.get(key)
        if val:
            return str(val)
    return "UNCLAIMED"


def verdict_of(record: dict) -> str:
    return str(record.get("verdict") or record.get("status") or "").upper()


def _shared_upstreams(rows: list[dict]) -> list[str]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        for up in set(row.get("upstreams") or []):
            counts[up] += 1
    return sorted(u for u, n in counts.items() if n >= 2)


def _probe_node_id(rid: str, pname: str, probe: Any) -> str:
    if isinstance(probe, dict):
        pid = str(
            probe.get("id")
            or probe.get("fingerprint")
            or f"{rid}:{pname}:{probe_fingerprint(probe)[:12]}"
        )
    else:
        pid = f"{rid}:{pname}:{probe_fingerprint(probe)[:12]}"
    return f"probe:{pid}"


def build(records: list[dict]) -> dict:
    """Build the directed graph and per-claim independence ranks.

    Rank is computed only over CONFIRMED records. Partition covers every
    record exactly once (per-claim components concatenated).
    """
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add_node(nid: str, ntype: str, **extra: Any) -> None:
        if nid not in nodes:
            row = {"id": nid, "type": ntype}
            row.update({k: v for k, v in extra.items() if v is not None})
            nodes[nid] = row

    normalized: list[dict] = []
    used_probe_nodes: set[str] = set()
    for i, rec in enumerate(records):
        rid = record_id_of(rec, f"record-{i}")
        cid = claim_id_of(rec)
        verd = verdict_of(rec)
        conf_node = f"confirmation:{rid}"
        add_node(
            conf_node,
            "confirmation",
            record_id=rid,
            claim_id=cid,
            verdict=verd,
        )
        upstreams: list[str] = []
        probe_ids: list[str] = []
        for pname, probe in probes_of(rec):
            if probe is None or probe == "":
                continue
            pnode = _probe_node_id(rid, pname, probe)
            if pnode in used_probe_nodes:
                pnode = f"{pnode}:{pname}"
            used_probe_nodes.add(pnode)
            probe_ids.append(pnode)
            meta: dict[str, Any] = {}
            if isinstance(probe, dict):
                meta = {
                    "shell": probe.get("shell"),
                    "field": probe.get("field"),
                    "tool": probe.get("tool"),
                    "engine": probe.get("engine"),
                    "fingerprint": probe.get("fingerprint") or probe_fingerprint(probe),
                }
            else:
                meta = {"fingerprint": probe_fingerprint(probe)}
            add_node(pnode, "probe", **meta)
            edges.append(
                {
                    "from": conf_node,
                    "to": pnode,
                    "kind": "uses-probe",
                    "via": pname,
                }
            )
            for up in extract_upstreams(probe):
                unode = f"upstream:{up}"
                add_node(unode, "upstream", key=up)
                edges.append(
                    {"from": pnode, "to": unode, "kind": "reads", "via": pname}
                )
                if up not in upstreams:
                    upstreams.append(up)
        normalized.append(
            {
                "record_id": rid,
                "claim_id": cid,
                "verdict": verd,
                "confirmation_node": conf_node,
                "probe_nodes": probe_ids,
                "upstreams": upstreams,
                "confirmer": rec.get("confirmer") or rec.get("confirmer_identity"),
            }
        )

    by_claim: dict[str, list[dict]] = defaultdict(list)
    for row in normalized:
        by_claim[row["claim_id"]].append(row)

    per_claim: list[dict] = []
    partition: list[dict] = []
    collapses: list[dict] = []

    for cid, rows in sorted(by_claim.items()):
        rec_by_id = {r["record_id"]: r for r in rows}

        uf_all = UnionFind()
        for row in rows:
            uf_all.add(row["record_id"])
        by_up: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            for up in row["upstreams"]:
                by_up[up].append(row["record_id"])
        for recs in by_up.values():
            head = recs[0]
            for other in recs[1:]:
                uf_all.union(head, other)
        comps_all = uf_all.components(r["record_id"] for r in rows)
        for root, members in sorted(comps_all.items(), key=lambda kv: kv[1]):
            partition.append(
                {
                    "claim_id": cid,
                    "component_id": f"{cid}:{root}",
                    "record_ids": members,
                    "size": len(members),
                    "shared_upstreams": _shared_upstreams(
                        [rec_by_id[m] for m in members]
                    ),
                }
            )

        confirmed = [r for r in rows if r["verdict"] == CONFIRMED]
        uf_c = UnionFind()
        for row in confirmed:
            uf_c.add(row["record_id"])
        by_up_c: dict[str, list[str]] = defaultdict(list)
        sourced = 0
        for row in confirmed:
            if row["upstreams"]:
                sourced += 1
                for up in row["upstreams"]:
                    by_up_c[up].append(row["record_id"])
        for recs in by_up_c.values():
            head = recs[0]
            for other in recs[1:]:
                uf_c.union(head, other)
        comps_c = (
            uf_c.components(r["record_id"] for r in confirmed) if confirmed else {}
        )
        independent_sets: list[dict] = []
        rank = 0
        for root, members in sorted(comps_c.items(), key=lambda kv: kv[1]):
            member_rows = [rec_by_id[m] for m in members]
            if not any(r["upstreams"] for r in member_rows):
                continue
            rank += 1
            shared = _shared_upstreams(member_rows)
            independent_sets.append(
                {
                    "component_id": f"{cid}:{root}",
                    "record_ids": members,
                    "upstreams": sorted(
                        {u for r in member_rows for u in r["upstreams"]}
                    ),
                    "shared_upstreams": shared,
                }
            )
            if len(members) > 1:
                collapses.append(
                    {
                        "claim_id": cid,
                        "rank_component": rank,
                        "component_record_ids": members,
                        "shared_upstream_nodes": [f"upstream:{u}" for u in shared],
                        "shared_upstreams": shared,
                        "confirmer_count": len(members),
                        "note": (
                            "Multiple confirmations share these upstream "
                            "inputs and therefore count as one signal."
                        ),
                    }
                )

        apparent_n = len(confirmed)
        for c in collapses:
            if c["claim_id"] == cid and "apparent_n" not in c:
                c["apparent_n"] = apparent_n
                c["rank"] = rank

        per_claim.append(
            {
                "claim_id": cid,
                "apparent_n": apparent_n,
                "rank": rank,
                "sourced_confirmed": sourced,
                "total_records": len(rows),
                "independent_sets": independent_sets,
                "collapsed": apparent_n > rank,
            }
        )

    rank_distribution: dict[str, int] = defaultdict(int)
    for row in per_claim:
        rank_distribution[str(row["rank"])] += 1

    assigned: list[str] = []
    for ns in partition:
        assigned.extend(ns["record_ids"])
    all_ids = [r["record_id"] for r in normalized]
    partition_ok = sorted(assigned) == sorted(all_ids) and len(assigned) == len(
        set(assigned)
    )

    rank1_collapses = [
        {
            "claim_id": row["claim_id"],
            "apparent_n": row["apparent_n"],
            "rank": row["rank"],
            "shared_upstreams": sorted(
                {
                    u
                    for s in row["independent_sets"]
                    for u in (s.get("shared_upstreams") or [])
                }
            ),
            "shared_upstream_nodes": [
                f"upstream:{u}"
                for s in row["independent_sets"]
                for u in (s.get("shared_upstreams") or [])
            ],
            "independent_sets": row["independent_sets"],
        }
        for row in per_claim
        if row["rank"] == 1 and row["apparent_n"] > 1
    ]

    return {
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "edges": edges,
        "normalized_records": normalized,
        "per_claim": per_claim,
        "partition": partition,
        "rank_distribution": dict(
            sorted(rank_distribution.items(), key=lambda kv: int(kv[0]))
        ),
        "collapses": collapses,
        "rank1_collapses": rank1_collapses,
        "partition_ok": partition_ok,
        "record_count": len(normalized),
        "partition_assigned_count": len(assigned),
    }


def claim_rank(result: dict, claim_id: str) -> dict | None:
    for row in result.get("per_claim") or []:
        if row.get("claim_id") == claim_id:
            return row
    return None


def ranks_from_edge_list(
    edges: list[dict],
    records: list[dict],
    *,
    confirmed_only: bool = True,
) -> dict[str, dict]:
    """Independent recompute used by probe 2.

    Does not call UnionFind. Inverts confirmation->probe->upstream edges
    into an upstream index, then DFS-connects confirmations that share an
    upstream. Must agree with build() ranks.
    """
    uses: dict[str, list[str]] = defaultdict(list)
    reads: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        kind = edge.get("kind")
        frm, to = edge.get("from") or "", edge.get("to") or ""
        if kind == "uses-probe":
            uses[frm].append(to)
        elif kind == "reads":
            reads[frm].append(to)

    conf_up: dict[str, set[str]] = {}
    rec_meta: dict[str, dict] = {}
    for i, rec in enumerate(records):
        rid = record_id_of(rec, f"record-{i}")
        cnode = f"confirmation:{rid}"
        ups: set[str] = set()
        for probe_node in uses.get(cnode, []):
            ups.update(reads.get(probe_node, []))
        conf_up[cnode] = ups
        rec_meta[cnode] = {
            "record_id": rid,
            "claim_id": claim_id_of(rec),
            "verdict": verdict_of(rec),
        }

    by_claim: dict[str, list[str]] = defaultdict(list)
    for cnode, meta in rec_meta.items():
        if confirmed_only and meta["verdict"] != CONFIRMED:
            continue
        by_claim[meta["claim_id"]].append(cnode)

    out: dict[str, dict] = {}
    for cid, cnodes in by_claim.items():
        adj: dict[str, set[str]] = {n: set() for n in cnodes}
        up_index: dict[str, list[str]] = defaultdict(list)
        for node in cnodes:
            for up in conf_up[node]:
                up_index[up].append(node)
        for group in up_index.values():
            for a in group:
                for b in group:
                    if a != b:
                        adj[a].add(b)
        seen: set[str] = set()
        comps: list[list[str]] = []
        for node in cnodes:
            if node in seen:
                continue
            stack = [node]
            seen.add(node)
            comp: list[str] = []
            while stack:
                cur = stack.pop()
                comp.append(cur)
                for nxt in adj[cur]:
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
            comps.append(sorted(comp))
        rank = 0
        for comp in comps:
            if any(conf_up[n] for n in comp):
                rank += 1
        out[cid] = {
            "claim_id": cid,
            "rank": rank,
            "apparent_n": len(cnodes),
            "components": comps,
        }
    return out
