"""Executable graph-invariant suite for WFA-0082.

Five invariants. Each has a targeted mutation that turns exactly that
invariant red. Cycle detection here is DFS; recount.py uses Kahn.
"""
from __future__ import annotations

import json

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

INVARIANT_IDS = (
    "referential_closure",
    "required_symmetry",
    "required_acyclicity",
    "namespace_disjointness",
    "anchor_presence",
)

DAG_RELS = frozenset({"implements", "requires", "derives-from"})
SYM_RELS = frozenset({"compat", "conflicts-with", "substitutes-for"})
DAG_RELS = DAG_RELS
SYM_RELS = SYM_RELS


def _violations_closure(bundle: dict) -> list[dict]:
    bad: list[dict] = []
    for surface, doc in bundle.items():
        ids = node_ids(doc)
        for src, dst, rel in iter_edges(doc):
            if src not in ids:
                bad.append(
                    {
                        "surface": surface,
                        "missing": src,
                        "edge": [src, dst, rel],
                        "why": "source-not-a-node",
                    }
                )
            if dst not in ids:
                bad.append(
                    {
                        "surface": surface,
                        "missing": dst,
                        "edge": [src, dst, rel],
                        "why": "target-not-a-node",
                    }
                )
    comp_ids = node_ids(bundle.get("component") or {})
    for rec in nodes_of(bundle.get("registry") or {}):
        rid = str(rec["id"])
        for mech in rec.get("mechanisms") or []:
            token = str(mech)
            if token not in comp_ids:
                bad.append(
                    {
                        "surface": "registry",
                        "missing": token,
                        "record": rid,
                        "why": "uses-mechanism-unresolved",
                    }
                )
    return bad


def _violations_symmetry(bundle: dict) -> list[dict]:
    bad: list[dict] = []
    for surface, doc in bundle.items():
        present = {
            (src, dst, rel)
            for src, dst, rel in iter_edges(doc)
            if rel in SYM_RELS
        }
        for src, dst, rel in present:
            if (dst, src, rel) not in present:
                bad.append(
                    {
                        "surface": surface,
                        "relation": rel,
                        "missing_reverse": [dst, src, rel],
                        "have": [src, dst, rel],
                    }
                )
    return bad


def _has_cycle_dfs(adj: dict[str, list[str]]) -> list[str] | None:
    white, grey, black = 0, 1, 2
    color = {n: white for n in adj}
    stack: list[str] = []

    def walk(node: str) -> list[str] | None:
        color[node] = grey
        stack.append(node)
        for nxt in adj[node]:
            if color.get(nxt, white) == grey:
                return stack[stack.index(nxt) :] + [nxt]
            if color.get(nxt, white) == white:
                color.setdefault(nxt, white)
                adj.setdefault(nxt, [])
                found = walk(nxt)
                if found:
                    return found
        stack.pop()
        color[node] = black
        return None

    for node in list(adj):
        if color[node] == white:
            found = walk(node)
            if found:
                return found
    return None


def _violations_acyclicity(bundle: dict) -> list[dict]:
    bad: list[dict] = []
    for surface, doc in bundle.items():
        adj: dict[str, list[str]] = {n: [] for n in node_ids(doc)}
        for src, dst, rel in iter_edges(doc):
            if rel not in DAG_RELS:
                continue
            adj.setdefault(src, []).append(dst)
            adj.setdefault(dst, [])
        cycle = _has_cycle_dfs(adj)
        if cycle:
            bad.append({"surface": surface, "cycle": cycle, "rels": sorted(DAG_RELS)})
    return bad


def _violations_namespace(bundle: dict) -> list[dict]:
    kinds: dict[str, set[str]] = {}
    homes: dict[str, set[str]] = {}
    for surface, node in all_nodes(bundle):
        nid = str(node["id"])
        kinds.setdefault(nid, set()).add(node_kind(node) or "<empty>")
        homes.setdefault(nid, set()).add(surface)
    bad: list[dict] = []
    for nid, kset in kinds.items():
        if len(kset) > 1:
            bad.append(
                {
                    "id": nid,
                    "kinds": sorted(kset),
                    "surfaces": sorted(homes[nid]),
                    "why": "same-id-multiple-kinds",
                }
            )
        expected = None
        for prefix, kind in PREFIX_KIND.items():
            if nid.startswith(prefix):
                expected = kind
                break
        observed = next(iter(kset)) if len(kset) == 1 else None
        if expected and observed and observed != expected:
            bad.append(
                {
                    "id": nid,
                    "expected_kind": expected,
                    "observed_kind": observed,
                    "why": "prefix-kind-mismatch",
                }
            )
    return bad


def _violations_anchor(bundle: dict) -> list[dict]:
    bad: list[dict] = []
    for surface, node in all_nodes(bundle):
        if not node_anchor(node).strip():
            bad.append(
                {
                    "surface": surface,
                    "id": str(node["id"]),
                    "why": "missing-or-empty-anchor",
                }
            )
    return bad


CHECKERS = {
    "referential_closure": _violations_closure,
    "required_symmetry": _violations_symmetry,
    "required_acyclicity": _violations_acyclicity,
    "namespace_disjointness": _violations_namespace,
    "anchor_presence": _violations_anchor,
}


def evaluate(bundle: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for inv in INVARIANT_IDS:
        viol = CHECKERS[inv](bundle)
        out[inv] = {
            "id": inv,
            "green": len(viol) == 0,
            "n_violations": len(viol),
            "violations": viol,
        }
    return out


def greens(result: dict[str, dict]) -> set[str]:
    return {k for k, v in result.items() if v["green"]}


def reds(result: dict[str, dict]) -> set[str]:
    return {k for k, v in result.items() if not v["green"]}


def mutate_closure(bundle: dict) -> dict:
    b = clone_bundle(bundle)
    recs = b["registry"]["records"]
    recs[0]["mechanisms"] = list(recs[0].get("mechanisms") or []) + ["mech-absent"]
    return b


def mutate_symmetry(bundle: dict) -> dict:
    b = clone_bundle(bundle)
    b["merge_map"]["edges"] = [
        e
        for e in b["merge_map"]["edges"]
        if not (
            e.get("source") == "wf-alpha"
            and e.get("target") == "wf-beta"
            and e.get("relation") == "compat"
        )
    ]
    return b


def mutate_acyclicity(bundle: dict) -> dict:
    b = clone_bundle(bundle)
    b["component"]["edges"] = list(b["component"]["edges"]) + [
        {
            "source": "mech-stage-gate",
            "target": "mech-licence-fetch",
            "relation": "requires",
        }
    ]
    return b


def mutate_namespace(bundle: dict) -> dict:
    b = clone_bundle(bundle)
    b["component"]["nodes"] = list(b["component"]["nodes"]) + [
        {
            "id": "wf-alpha",
            "kind": "mechanism",
            "anchor": "planted-namespace-collision",
        }
    ]
    return b


def mutate_anchor(bundle: dict) -> dict:
    b = clone_bundle(bundle)
    for node in b["provenance"]["nodes"]:
        if node.get("id") == "lic-mit":
            node["anchor"] = ""
            break
    return b


MUTATIONS = (
    {
        "id": "mut-dangling-mechanism",
        "invariant": "referential_closure",
        "apply": mutate_closure,
        "how": (
            "Cite mech-absent from wf-alpha in the registry. Closure must go "
            "red; other invariants do not inspect that citation."
        ),
    },
    {
        "id": "mut-drop-compat-reverse",
        "invariant": "required_symmetry",
        "apply": mutate_symmetry,
        "how": (
            "Delete the wf-alpha->wf-beta compat edge, leaving a one-sided "
            "declaration on the merge map."
        ),
    },
    {
        "id": "mut-requires-back-edge",
        "invariant": "required_acyclicity",
        "apply": mutate_acyclicity,
        "how": (
            "Add mech-stage-gate requires mech-licence-fetch, cycling the "
            "existing requires edge. conflicts-with symmetry is unchanged."
        ),
    },
    {
        "id": "mut-reuse-workflow-id-as-mechanism",
        "invariant": "namespace_disjointness",
        "apply": mutate_namespace,
        "how": (
            "Plant a mechanism node whose id is wf-alpha, colliding with the "
            "workflow of the same token."
        ),
    },
    {
        "id": "mut-strip-licence-anchor",
        "invariant": "anchor_presence",
        "apply": mutate_anchor,
        "how": "Blank the licence-class node anchor on the provenance graph.",
    },
)


def mutation_battery(bundle: dict) -> dict:
    baseline = evaluate(bundle)
    baseline_red = reds(baseline)
    rows = []
    independent = True
    for spec in MUTATIONS:
        result = evaluate(spec["apply"](bundle))
        got_red = reds(result)
        want_red = {spec["invariant"]}
        ok = got_red == want_red
        if not ok:
            independent = False
        rows.append(
            {
                "id": spec["id"],
                "target_invariant": spec["invariant"],
                "how": spec["how"],
                "baseline_green": spec["invariant"] in greens(baseline),
                "mutant_red": spec["invariant"] in got_red,
                "exactly_one_red": got_red == want_red,
                "red_set": sorted(got_red),
                "green_set": sorted(greens(result)),
                "pass": ok,
                "violations": result[spec["invariant"]]["violations"],
            }
        )
    return {
        "baseline": baseline,
        "baseline_all_green": not baseline_red,
        "baseline_red": sorted(baseline_red),
        "mutations": rows,
        "mutation_independence": independent and not baseline_red,
        "n_invariants": len(INVARIANT_IDS),
        "n_mutations": len(rows),
        "n_mutations_passed": sum(1 for r in rows if r["pass"]),
    }


def crlf_roundtrip_stable(bundle: dict) -> dict:
    payload = json.dumps(bundle, sort_keys=True)
    lf = json.loads(payload)
    crlf = json.loads(payload.replace("\n", "\r\n") if "\n" in payload else payload)
    # Also re-parse a CRLF-encoded dump the way graphs.read_json does.
    raw_lf = payload.encode("utf-8")
    raw_crlf = payload.replace("\n", "\r\n").encode("utf-8")
    a = evaluate(json.loads(raw_lf.replace(b"\r\n", b"\n").replace(b"\r", b"\n")))
    b = evaluate(json.loads(raw_crlf.replace(b"\r\n", b"\n").replace(b"\r", b"\n")))
    same = greens(a) == greens(b) == greens(evaluate(lf)) == greens(evaluate(crlf))
    return {
        "stable": same,
        "lf_green": sorted(greens(a)),
        "crlf_green": sorted(greens(b)),
        "note": (
            "Loaders strip CR so a committed blob with CRLF or LF produces "
            "the same invariant verdicts."
        ),
    }


mutation_battery = mutation_battery
crlf_roundtrip_stable = crlf_roundtrip_stable
