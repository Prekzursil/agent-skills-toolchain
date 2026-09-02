#!/usr/bin/env python3
"""Named probe 1: settle the 466-node graph by reading cited sources.

Signal: dual-method (pathlib vs os.stat+open) node-by-node resolution.
Every UNRESOLVED survivor must carry a named blocker. A node whose name
matches a live file but whose cited_source is absent must stay UNRESOLVED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import graph as G  # noqa: E402
import settle as S  # noqa: E402

ART = (
    REPO
    / "command-center/foundry/WFA-0153-close-the-unresolved-nodes-in-the-466-node-provenanc.json"
)
UNIT = "WFA-0153"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    blob = json.dumps(doc)
    if "SUCCESS:WFA-0153" not in blob:
        return fail("sentinel absent")

    graph = G.load_graph(REPO, rebuild=False)
    if len(graph.get("nodes") or []) != G.NODE_TARGET:
        return fail("node cardinality", len(graph.get("nodes") or []))
    if len(graph.get("edges") or []) != G.EDGE_TARGET:
        return fail("edge cardinality", len(graph.get("edges") or []))

    a = S.settle_graph(REPO, graph, method="pathlib")
    b = S.settle_graph(REPO, graph, method="stat-open")
    if a["unresolved_count"] != b["unresolved_count"]:
        return fail("method disagreement unresolved_count", [a["unresolved_count"], b["unresolved_count"]])
    if a["resolved_ids_sha256"] != b["resolved_ids_sha256"]:
        return fail("method disagreement resolved_ids_sha256")
    if a["resolved_count"] < 1:
        return fail("no node resolved by reading a cited source")
    if a["unresolved_count"] < 1:
        return fail("expected unresolved survivors on this worktree")

    for row in a["survivors"]:
        if not row.get("blocker") or row["blocker"] not in S.BLOCKERS:
            return fail("survivor missing named blocker", row)
        if row.get("status") != "UNRESOLVED":
            return fail("survivor not UNRESOLVED", row)

    art_set = doc.get("settlement") or {}
    if art_set.get("unresolved_count") != a["unresolved_count"]:
        return fail("artifact unresolved_count != live", art_set)
    if art_set.get("resolved_count") != a["resolved_count"]:
        return fail("artifact resolved_count != live", art_set)
    if art_set.get("resolved_ids_sha256") != a["resolved_ids_sha256"]:
        return fail("artifact resolved_ids_sha256 != live")
    if art_set.get("methods_agree") is not True:
        return fail("artifact methods_agree")

    art_survivors = doc.get("survivors") or []
    if len(art_survivors) != a["unresolved_count"]:
        return fail("artifact survivor list length")
    live_ids = {r["node_id"] for r in a["survivors"]}
    art_ids = {r.get("node_id") for r in art_survivors}
    if live_ids != art_ids:
        return fail("artifact survivor ids != live")

    trap = next((n for n in graph["nodes"] if n.get("name_trap")), None)
    if trap is None:
        return fail("name-trap node missing")
    trap_v = next(v for v in a["verdicts"] if v["node_id"] == trap["id"])
    if trap_v["status"] != "UNRESOLVED":
        return fail("name-trap resolved — name was accepted as evidence", trap_v)
    name_hits = [
        p.relative_to(REPO).as_posix()
        for p in REPO.rglob(trap["name"])
        if p.is_file() and "/WFA-0153/" not in p.as_posix()
    ]
    if not name_hits:
        return fail("name-trap basename not present on worktree", trap["name"])
    nne = doc.get("name_not_evidence") or {}
    if nne.get("status") != "UNRESOLVED" or nne.get("name_exists_on_worktree") is not True:
        return fail("artifact name_not_evidence", nne)

    ginfo = doc.get("graph") or {}
    if ginfo.get("node_count") != G.NODE_TARGET or ginfo.get("edge_count") != G.EDGE_TARGET:
        return fail("artifact graph cardinality", ginfo)

    finding = doc.get("finding_unresolved_provenance") or {}
    refs = finding.get("unresolved_refs") or []
    if len(refs) != G.UNRESOLVED_REF_COUNT:
        return fail("FINDING unresolved_refs count", len(refs))
    if not finding.get("settling_probe"):
        return fail("FINDING settling_probe missing")

    out = {
        "probe": "probe1-settle",
        "unit_id": UNIT,
        "pass": True,
        "nodes": G.NODE_TARGET,
        "edges": G.EDGE_TARGET,
        "resolved": a["resolved_count"],
        "unresolved": a["unresolved_count"],
        "methods_agree": True,
        "survivors_named_blockers": True,
        "name_trap_unresolved": True,
        "name_trap_hits": name_hits[:5],
        "resolved_ids_sha256": a["resolved_ids_sha256"],
    }
    (HERE / "probe1-settle.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print(
        f"resolved={a['resolved_count']} unresolved={a['unresolved_count']} "
        f"name_trap=UNRESOLVED methods_agree=True"
    )
    print("SUCCESS:WFA-0153-probe1 settle named-blockers name-trap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
