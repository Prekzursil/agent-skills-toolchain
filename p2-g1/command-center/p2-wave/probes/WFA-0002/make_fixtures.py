#!/usr/bin/env python3
"""WFA-0002 fixture-corpus generator (deterministic, idempotent).

Builds the fixture-control corpus the closure checker re-verifies on THIS
worktree:
  fixtures/graph.json      - 40 distinct refs over 66 unresolved edges
  fixtures/registry.json   - instrument B: the head-index candidate registry
  fixtures/estate/**       - instrument A: the live estate tree (filesystem)
  fixtures/head-blobs/*    - repo-only bodies only B can see

The original corpus was built on a Linux worktree (paths /opt/p2/...); this
generator re-materializes the SAME structure with fresh bytes; live hashes
are recorded by the probes, never asserted equal to the original run.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

FIX = Path(__file__).resolve().parent / "fixtures"

ADD_NAMES = (
    ["wfa0002-skill-a-01", "wfa0002-skill-a-02", "wfa0002-skill-a-03"]
    + ["wfa0002-skill-b-01", "wfa0002-skill-b-02", "wfa0002-skill-b-03"]
    + ["wfa0002-rule-01", "wfa0002-rule-02"]
    + ["wfa0002-plugin-01", "wfa0002-plugin-02"]
    + ["wfa0002-workflow-01", "wfa0002-workflow-02"]
    + ["wfa0002-liveonly-%02d" % i for i in range(1, 9)]
    + ["wfa0002-repoonly-%02d" % i for i in range(1, 9)]
)
PHANTOMS = ["wfa0002-phantom-%02d" % i for i in range(1, 13)]

# A-side layout: name -> (subtree, filename)
def estate_layout(name: str):
    if name.startswith("wfa0002-liveonly"):
        n = int(name.rsplit("-", 1)[-1])
        return [("skills-a", "SKILL.md"), ("skills-b", "SKILL.md"),
                ("rules", name + ".md"), ("plugins", "plugin.json")][(n - 1) % 4]
    if name.startswith("wfa0002-skill-a"):
        return "skills-a", "SKILL.md"
    if name.startswith("wfa0002-skill-b"):
        return "skills-b", "SKILL.md"
    if name.startswith("wfa0002-rule"):
        return "rules", name + ".md"
    if name.startswith("wfa0002-plugin"):
        return "plugins", "plugin.json"
    if name.startswith("wfa0002-workflow"):
        return "workflows", name + ".json"
    return None, None


def body(name: str, live: bool) -> str:
    kind = "live-estate" if live else "head-blob"
    lines = [
        "---",
        "name: " + name,
        "description: WFA-0002 fixture-control corpus entry",
        "---",
        "",
        "# " + name,
        "",
        "Instrument: " + kind + ". Not a real skill; fixture only.",
        "",
    ]
    return "\n".join(lines)


def registry_relpath(name: str) -> str:
    sub, fname = estate_layout(name)
    if name.startswith("wfa0002-repoonly"):
        return "head-blobs/" + name + ".body"
    if sub in ("skills-a", "skills-b"):
        return sub + "/" + name + "/SKILL.md"
    if sub == "rules":
        return sub + "/" + name + ".md"
    if sub == "plugins":
        return sub + "/" + name + "/plugin.json"
    if sub == "workflows":
        return sub + "/" + name + ".json"
    raise ValueError(name)


EDGE_MULTIPLICITY = {}
for _n in ADD_NAMES:
    EDGE_MULTIPLICITY[_n] = 2
for _n in ("wfa0002-liveonly-01", "wfa0002-liveonly-02", "wfa0002-liveonly-03",
           "wfa0002-liveonly-04", "wfa0002-liveonly-05", "wfa0002-liveonly-06"):
    EDGE_MULTIPLICITY[_n] = 3
for _n in ("wfa0002-liveonly-07", "wfa0002-liveonly-08"):
    EDGE_MULTIPLICITY[_n] = 2
for _n in ("wfa0002-repoonly-01", "wfa0002-repoonly-02", "wfa0002-repoonly-03",
           "wfa0002-repoonly-04", "wfa0002-repoonly-05", "wfa0002-repoonly-06",
           "wfa0002-repoonly-07", "wfa0002-repoonly-08"):
    EDGE_MULTIPLICITY[_n] = 1
for _n in PHANTOMS:
    EDGE_MULTIPLICITY[_n] = 1


def build() -> dict:
    import shutil
    if (FIX / "estate").exists():
        shutil.rmtree(FIX / "estate")
    for sub in ("skills-a", "skills-b", "rules", "plugins", "workflows"):
        (FIX / "estate" / sub).mkdir(parents=True, exist_ok=True)
    (FIX / "head-blobs").mkdir(parents=True, exist_ok=True)

    registry_rows = []
    for name in ADD_NAMES:
        sub, fname = estate_layout(name)
        if name.startswith("wfa0002-repoonly"):
            dst = FIX / "head-blobs" / (name + ".body")
            rel = "head-blobs/" + name + ".body"
        elif sub in ("skills-a", "skills-b", "plugins"):
            dst = FIX / "estate" / sub / name / fname
            rel = registry_relpath(name)
        else:
            dst = FIX / "estate" / sub / fname
            rel = registry_relpath(name)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(body(name, live=not name.startswith("wfa0002-repoonly")),
                       encoding="utf-8", newline="")
        raw = dst.read_bytes().replace(b"\r", b"\n")
        if not name.startswith("wfa0002-liveonly"):
            registry_rows.append({
                "id": "wf-" + name,
                "name": name,
                "path": rel,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            })

    edges = []
    i = 0
    for name in ADD_NAMES + PHANTOMS:
        for _ in range(EDGE_MULTIPLICITY[name]):
            i += 1
            edges.append({
                "edge_id": "E-%03d" % i,
                "blueprint": "BP-WFA0002-%03d" % i,
                "ref": name,
                "prov": "unresolved",
            })
    assert len(edges) == 66, len(edges)
    graph = {
        "record_type": "fixture-provenance-graph",
        "not_the_live_466_node_graph": True,
        "distinct_refs": len(set(e["ref"] for e in edges)),
        "unresolved_edges": len(edges),
        "edges": edges,
    }
    (FIX / "graph.json").write_text(json.dumps(graph, indent=1), encoding="utf-8", newline="")
    registry = {
        "record_type": "fixture-candidate-registry",
        "note": "instrument B: independent head-index; liveonly entries absent by construction",
        "candidates": registry_rows,
    }
    (FIX / "registry.json").write_text(json.dumps(registry, indent=1), encoding="utf-8", newline="")
    return {"refs": len(set(e["ref"] for e in edges)), "edges": len(edges), "registry_rows": len(registry_rows)}


if __name__ == "__main__":
    import sys
    print(json.dumps(build()))
