#!/usr/bin/env python3
"""Probe 2 (independent): partition, non-isomorphism, worked substitutions.

Recomputes undirected components with its own BFS (does not call
semantic_graph.undirected_components). Both-states: a planted requires-chain
must make spanning=true and the detector must fire; live graph must not span.
"""
from __future__ import annotations

import copy
import json
import sys
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]

ART = REPO / "command-center/wfa/WFA-0080-semantic-component-graph.json"
SIG = HERE / "fixtures/workflow_compat_signature.json"


def bfs_components(node_ids: list[str], edges: list[dict]) -> list[list[str]]:
    adj = {n: set() for n in node_ids}
    for e in edges:
        if e["source"] in adj and e["target"] in adj:
            adj[e["source"]].add(e["target"])
            adj[e["target"]].add(e["source"])
    seen: set[str] = set()
    comps: list[list[str]] = []
    for start in node_ids:
        if start in seen:
            continue
        q = deque([start])
        seen.add(start)
        members: list[str] = []
        while q:
            u = q.popleft()
            members.append(u)
            for v in sorted(adj[u]):
                if v not in seen:
                    seen.add(v)
                    q.append(v)
        comps.append(sorted(members))
    comps.sort(key=lambda c: (-len(c), c[0]))
    return comps


def spanning(n_nodes: int, largest: int) -> bool:
    return n_nodes > 1 and largest == n_nodes


def iso_reasons(doc: dict, sig: dict, comps: list[list[str]]) -> list[str]:
    reasons: list[str] = []
    n_nodes = len(doc["nodes"])
    n_comp = len(comps)
    largest = len(comps[0]) if comps else 0
    rels = {e["relation"] for e in doc["edges"]}
    if n_nodes != int(sig["n_nodes"]):
        reasons.append(f"|V| {n_nodes} != workflow {sig['n_nodes']}")
    if n_comp != int(sig["n_components"]):
        reasons.append(f"components {n_comp} != workflow {sig['n_components']}")
    if largest != int(sig["largest_component"]):
        reasons.append(f"largest {largest} != workflow {sig['largest_component']}")
    if doc.get("node_kind") != sig["node_kind"]:
        reasons.append(f"node_kind {doc.get('node_kind')} != {sig['node_kind']}")
    if rels != set(sig["edge_relations"]):
        reasons.append(f"relations {sorted(rels)} != {sorted(sig['edge_relations'])}")
    if sig.get("expresses_substitution") is False and "substitutes-for" in rels:
        reasons.append("this graph expresses substitutes-for; workflow compat cannot")
    return reasons


def substitution_errors(doc: dict) -> list[str]:
    bad: list[str] = []
    for e in doc["edges"]:
        if e.get("relation") != "substitutes-for":
            continue
        ws = e.get("worked_substitution")
        if not isinstance(ws, dict):
            bad.append(f"{e['id']}: missing worked_substitution")
            continue
        if ws.get("not_justified_by") != "similarity":
            bad.append(f"{e['id']}: not_justified_by is not similarity-refusal")
        construction = str(ws.get("construction") or "")
        rewrite = str(ws.get("ir_rewrite") or "")
        if len(construction) < 80:
            bad.append(f"{e['id']}: construction too short")
        blob = (construction + " " + rewrite + " " + str(e.get("justification") or "")).lower()
        src_tok = e["source"].split(".", 1)[-1].replace("-", " ")
        tgt_tok = e["target"].split(".", 1)[-1].replace("-", " ")
        # Worked rewrite must name both ends (slug tokens).
        if src_tok.split()[0] not in blob and e["source"] not in blob:
            bad.append(f"{e['id']}: construction does not name source {e['source']}")
        if tgt_tok.split()[0] not in blob and e["target"] not in blob:
            bad.append(f"{e['id']}: construction does not name target {e['target']}")
        if not ws.get("capability_preserved") or not ws.get("capability_lost"):
            bad.append(f"{e['id']}: substitution must name preserved and lost capability")
    return bad


def main() -> int:
    if not ART.is_file():
        print("FAILED:WFA-0080-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    sig = json.loads(SIG.read_text(encoding="utf-8"))
    ids = [n["id"] for n in doc["nodes"]]
    comps = bfs_components(ids, doc["edges"])
    sizes = [len(c) for c in comps]
    live_span = spanning(len(ids), sizes[0] if sizes else 0)
    declared = doc.get("component_report") or {}
    reasons = iso_reasons(doc, sig, comps)
    sub_errs = substitution_errors(doc)
    n_sub = sum(1 for e in doc["edges"] if e.get("relation") == "substitutes-for")

    print(f"INDEPENDENT_BFS components={len(comps)} sizes={sizes}")
    print(f"DECLARED count={declared.get('count')} sizes={declared.get('sizes')}")
    print(f"SPANNING live={live_span} declared={declared.get('spanning')}")
    print(f"ISO_REASONS n={len(reasons)} {reasons}")
    print(f"SUBSTITUTES_FOR n={n_sub} errors={sub_errs}")
    print(f"WORKFLOW_SIG nodes={sig['n_nodes']} components={sig['n_components']}")

    if declared.get("count") != len(comps) or declared.get("sizes") != sizes:
        print("FAILED:WFA-0080-probe2 declared component report != independent BFS")
        return 1
    if live_span or declared.get("spanning") is True:
        print("FAILED:WFA-0080-probe2 live graph is a spanning component (FINDING, not shippable)")
        return 1
    if len(comps) < 2:
        print("FAILED:WFA-0080-probe2 graph does not partition")
        return 1
    if len(declared.get("explanation") or "") < 80:
        print("FAILED:WFA-0080-probe2 partition explanation missing")
        return 1
    if not reasons:
        print("FAILED:WFA-0080-probe2 failed to distinguish from workflow compat graph")
        return 1
    if n_sub < 3 or sub_errs:
        print("FAILED:WFA-0080-probe2 substitutes-for " + (sub_errs[0] if sub_errs else "count"))
        return 1

    mutant = copy.deepcopy(doc)
    extra = []
    for a, b in zip(ids, ids[1:]):
        extra.append(
            {
                "id": f"e:planted-span:{a}->{b}",
                "source": a,
                "target": b,
                "relation": "requires",
                "justification": "planted spanning chain",
            }
        )
    mutant["edges"] = list(mutant["edges"]) + extra
    m_comps = bfs_components(ids, mutant["edges"])
    m_span = spanning(len(ids), len(m_comps[0]))
    if not m_span:
        print("FAILED:WFA-0080-probe2 spanning mutant did not produce one component")
        return 1
    if live_span:
        print("FAILED:WFA-0080-probe2 detector cannot tell spanning from partitioned")
        return 1

    print(
        "NEGATIVE CONTROL verbatim: planted requires-chain makes independent "
        f"BFS spanning=true (components={len(m_comps)}, largest={len(m_comps[0])}); "
        f"live graph spanning=false (components={len(comps)}, largest={sizes[0]})."
    )
    print(
        "BOTH-STATES: FIRED on spanning mutant; SILENT on live partitioned graph; "
        "not isomorphic to 108-node 1-component compat signature; "
        f"{n_sub} substitutes-for carry worked substitutions."
    )
    print("SUCCESS:WFA-0080-probe2 independent-bfs not-isomorphic worked-substitution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
