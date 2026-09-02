#!/usr/bin/env python3
"""Probe 1: recompute counts from the emitted graph on a separate code path.

Evidence A: declared 530, undirected 265, asymmetric 0, fusible < naive.
Both-states: drop one reciprocal declaration in memory; asymmetric must go red
while the undirected edge set size stays 265.
"""
from __future__ import annotations

import copy
import json
import sys
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/wfa/WFA-0081-merge-compatibility-map-v2.json"


def undirected_from_nodes(nodes: list[dict]) -> set[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for n in nodes:
        a = n["id"]
        for b in n.get("compat") or []:
            lo, hi = (a, b) if a < b else (b, a)
            if lo != hi:
                edges.add((lo, hi))
    return edges


def declared_count(nodes: list[dict]) -> int:
    return sum(len(n.get("compat") or []) for n in nodes)


def asymmetric_count(nodes: list[dict]) -> int:
    by = {n["id"]: set(n.get("compat") or []) for n in nodes}
    n_asym = 0
    for a, neigh in by.items():
        for b in neigh:
            if a not in by.get(b, set()):
                n_asym += 1
    return n_asym


def components(ids: list[str], undirected: set[tuple[str, str]]) -> list[int]:
    adj = {i: set() for i in ids}
    for a, b in undirected:
        adj[a].add(b)
        adj[b].add(a)
    seen: set[str] = set()
    sizes: list[int] = []
    for start in ids:
        if start in seen:
            continue
        q = deque([start])
        seen.add(start)
        n = 1
        while q:
            u = q.popleft()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    q.append(v)
                    n += 1
        sizes.append(n)
    sizes.sort(reverse=True)
    return sizes


def recount(doc: dict) -> dict:
    nodes = doc["nodes"]
    ids = [n["id"] for n in nodes]
    undirected = undirected_from_nodes(nodes)
    declared = declared_count(nodes)
    asymmetric = asymmetric_count(nodes)
    hard_pairs: set[tuple[str, str]] = set()
    for e in doc.get("edges") or []:
        if e.get("kind") != "conflicts-with":
            continue
        if e.get("grade") != "HARD" or not e.get("subtracts_from_fusible"):
            continue
        a, b = e["source"], e["target"]
        hard_pairs.add((a, b) if a < b else (b, a))
    fusible = undirected - hard_pairs
    listed = {tuple(p) if p[0] < p[1] else (p[1], p[0]) for p in doc.get("fusible_pairs") or []}
    removed = doc.get("conflict_subtraction", {}).get("pairs_removed") or []
    return {
        "nodes": len(nodes),
        "declared": declared,
        "undirected": len(undirected),
        "asymmetric": asymmetric,
        "hard_on_compat": len(hard_pairs & undirected),
        "pairs_removed": len(removed),
        "fusible": len(fusible),
        "listed_fusible": len(listed),
        "listed_matches": listed == fusible,
        "compat_sizes": components(ids, undirected),
        "fusible_sizes": components(ids, fusible),
        "honesty_zero_merges": (doc.get("honesty") or {}).get("merges_executed") == 0,
        "honesty_statement": "no merge has yet been executed"
        in str((doc.get("honesty") or {}).get("statement") or "").lower(),
    }


def main() -> int:
    if not ART.is_file():
        print("FAILED:WFA-0081-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0081" not in text:
        print("FAILED:WFA-0081-probe1 sentinel-absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0081-probe1 self-declared", doc.get("state"))
        return 1
    c = recount(doc)
    print(json.dumps(c, sort_keys=True))
    if c["declared"] != 530 or c["undirected"] != 265 or c["asymmetric"] != 0:
        print(
            f"FAILED:WFA-0081-probe1 counts declared={c['declared']} "
            f"undirected={c['undirected']} asymmetric={c['asymmetric']}"
        )
        return 1
    if not (c["fusible"] < c["undirected"]):
        print("FAILED:WFA-0081-probe1 fusible not strictly less than naive compat")
        return 1
    if c["pairs_removed"] != c["hard_on_compat"] or c["pairs_removed"] <= 0:
        print("FAILED:WFA-0081-probe1 conflict subtraction not visible")
        return 1
    if not c["listed_matches"]:
        print("FAILED:WFA-0081-probe1 listed fusible_pairs != recomputed set")
        return 1
    if c["compat_sizes"] != [108]:
        print(f"FAILED:WFA-0081-probe1 compat components {c['compat_sizes']}")
        return 1
    if len(c["fusible_sizes"]) < 2:
        print(f"FAILED:WFA-0081-probe1 fusible did not partition {c['fusible_sizes']}")
        return 1
    if not c["honesty_zero_merges"] or not c["honesty_statement"]:
        print("FAILED:WFA-0081-probe1 honesty block missing")
        return 1
    mus = (doc.get("v1_merge_units_recheck") or {}).get("units") or []
    if len(mus) != 30:
        print(f"FAILED:WFA-0081-probe1 merge units {len(mus)} want 30")
        return 1
    if not (doc.get("v1_merge_units_recheck") or {}).get("now_illegal"):
        print("FAILED:WFA-0081-probe1 no now-illegal merge reported")
        return 1

    mutant = copy.deepcopy(doc)
    victim = next(n for n in mutant["nodes"] if n.get("compat"))
    dropped = victim["compat"].pop()
    m = recount(mutant)
    if m["asymmetric"] <= 0:
        print("FAILED:WFA-0081-probe1 both-states: dropping a reciprocal stayed symmetric")
        return 1
    if m["undirected"] != 265:
        print(
            f"FAILED:WFA-0081-probe1 both-states: undirected moved {m['undirected']} "
            f"(content created or lost); dropped={dropped}"
        )
        return 1
    print(
        f"both_states_asymmetric={m['asymmetric']} undirected_invariant=265 "
        f"dropped={victim['id']}->{dropped}"
    )
    print("SUCCESS:WFA-0081-probe1 recomputed counts and both-states asymmetry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
