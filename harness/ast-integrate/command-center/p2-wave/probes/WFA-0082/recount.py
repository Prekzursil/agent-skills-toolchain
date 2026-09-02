"""Independent recount of WFA-0082 invariants.

Uses set-difference closure, reverse-pair symmetry, and Kahn's algorithm
for acyclicity. Does not call suite.evaluate.
"""
from __future__ import annotations

from collections import defaultdict, deque

from graphs import (
    PREFIX_KIND,
    all_nodes,
    clone_bundle,
    iter_edges,
    node_anchor,
    node_ids,
    node_kind,
    nodes_of,
)

DAG_RELS = frozenset({"implements", "requires", "derives-from"})
SYM_RELS = frozenset({"compat", "conflicts-with", "substitutes-for"})
IDS = (
    "referential_closure",
    "required_symmetry",
    "required_acyclicity",
    "namespace_disjointness",
    "anchor_presence",
)


def closure_green(bundle: dict) -> bool:
    missing: set[str] = set()
    for doc in bundle.values():
        ids = node_ids(doc)
        ends: set[str] = set()
        for src, dst, _rel in iter_edges(doc):
            ends.add(src)
            ends.add(dst)
        missing |= ends - ids
    comp = node_ids(bundle.get("component") or {})
    cited: set[str] = set()
    for rec in nodes_of(bundle.get("registry") or {}):
        for mech in rec.get("mechanisms") or []:
            cited.add(str(mech))
    missing |= cited - comp
    return not missing


def symmetry_green(bundle: dict) -> bool:
    for doc in bundle.values():
        have = {
            (src, dst, rel)
            for src, dst, rel in iter_edges(doc)
            if rel in SYM_RELS
        }
        for src, dst, rel in have:
            if (dst, src, rel) not in have:
                return False
    return True


def acyclicity_green(bundle: dict) -> bool:
    for doc in bundle.values():
        indeg: dict[str, int] = defaultdict(int)
        adj: dict[str, list[str]] = defaultdict(list)
        nodes = set(node_ids(doc))
        for src, dst, rel in iter_edges(doc):
            if rel not in DAG_RELS:
                continue
            nodes.add(src)
            nodes.add(dst)
            adj[src].append(dst)
            indeg[dst] += 1
        for n in nodes:
            indeg.setdefault(n, 0)
            adj.setdefault(n, [])
        q = deque([n for n in nodes if indeg[n] == 0])
        seen = 0
        while q:
            n = q.popleft()
            seen += 1
            for nxt in adj[n]:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    q.append(nxt)
        if seen != len(nodes):
            return False
    return True


def namespace_green(bundle: dict) -> bool:
    kinds: dict[str, set[str]] = defaultdict(set)
    for _surface, node in all_nodes(bundle):
        kinds[str(node["id"])].add(node_kind(node) or "<empty>")
    for nid, kset in kinds.items():
        if len(kset) > 1:
            return False
        expected = None
        for prefix, kind in PREFIX_KIND.items():
            if nid.startswith(prefix):
                expected = kind
                break
        observed = next(iter(kset))
        if expected and observed != expected:
            return False
    return True


def anchor_green(bundle: dict) -> bool:
    for _surface, node in all_nodes(bundle):
        if not node_anchor(node).strip():
            return False
    return True


CHECK = {
    "referential_closure": closure_green,
    "required_symmetry": symmetry_green,
    "required_acyclicity": acyclicity_green,
    "namespace_disjointness": namespace_green,
    "anchor_presence": anchor_green,
}


def evaluate(bundle: dict) -> dict[str, bool]:
    return {inv: CHECK[inv](bundle) for inv in IDS}


def greens(result: dict[str, bool]) -> set[str]:
    return {k for k, ok in result.items() if ok}


def reds(result: dict[str, bool]) -> set[str]:
    return {k for k, ok in result.items() if not ok}


def apply_mut_closure(bundle: dict) -> dict:
    b = clone_bundle(bundle)
    recs = b["registry"]["records"]
    recs[0]["mechanisms"] = list(recs[0].get("mechanisms") or []) + ["mech-absent"]
    return b


def apply_mut_symmetry(bundle: dict) -> dict:
    b = clone_bundle(bundle)
    b["merge_map"]["edges"] = [
        e
        for e in b["merge_map"]["edges"]
        if not (
            e.get("relation") == "compat"
            and e.get("source") == "wf-alpha"
            and e.get("target") == "wf-beta"
        )
    ]
    return b


def apply_mut_acyclicity(bundle: dict) -> dict:
    b = clone_bundle(bundle)
    b["component"]["edges"] = list(b["component"]["edges"]) + [
        {
            "source": "mech-stage-gate",
            "target": "mech-licence-fetch",
            "relation": "requires",
        }
    ]
    return b


def apply_mut_namespace(bundle: dict) -> dict:
    b = clone_bundle(bundle)
    b["component"]["nodes"] = list(b["component"]["nodes"]) + [
        {
            "id": "wf-alpha",
            "kind": "mechanism",
            "anchor": "planted-namespace-collision",
        }
    ]
    return b


def apply_mut_anchor(bundle: dict) -> dict:
    b = clone_bundle(bundle)
    nodes = []
    for node in b["provenance"]["nodes"]:
        n = dict(node)
        if n.get("id") == "lic-mit":
            n["anchor"] = "   "
        nodes.append(n)
    b["provenance"]["nodes"] = nodes
    return b


MUTATORS = (
    ("referential_closure", apply_mut_closure),
    ("required_symmetry", apply_mut_symmetry),
    ("required_acyclicity", apply_mut_acyclicity),
    ("namespace_disjointness", apply_mut_namespace),
    ("anchor_presence", apply_mut_anchor),
)


def battery(bundle: dict) -> dict:
    base = evaluate(bundle)
    rows = []
    ok = all(base.values())
    for inv, mut in MUTATORS:
        got = reds(evaluate(mut(bundle)))
        rows.append(
            {
                "target": inv,
                "red_set": sorted(got),
                "exactly_that": got == {inv},
            }
        )
        if got != {inv}:
            ok = False
    return {
        "baseline_all_green": all(base.values()),
        "baseline": base,
        "rows": rows,
        "pass": ok,
    }
