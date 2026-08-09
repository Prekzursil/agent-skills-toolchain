"""wfa-3 probe 1: extract the anchor slice + join it against the provenance/license graph.

Mechanical, no judgement. Prints the 32 anchor rows and whatever the provenance graph
already asserts about each, so licence/maintenance claims have a second source.
"""

import json
from pathlib import Path

CORPUS = Path("C:/Users/Prekzursil/.claude/harness-restore-20260806")
REG = CORPUS / "08-WORKFLOW-CANDIDATE-REGISTRY.json"
PROV = CORPUS / "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json"

reg = json.loads(REG.read_text(encoding="utf-8"))
cands = reg["candidates"]
assert len(cands) == 284, len(cands)

anchor = cands[64:96]  # 1-based 65..96
print(f"anchor rows: {len(anchor)}")

prov = json.loads(PROV.read_text(encoding="utf-8"))
nodes = prov["nodes"]
print("prov node fields:", sorted(nodes[0].keys()))
by_id = {}
for n in nodes:
    for key in ("id", "node_id", "candidate_id", "name"):
        if key in n and isinstance(n[key], str):
            by_id.setdefault(n[key], []).append(n)

print("\nprov counts keys:", json.dumps(prov["counts"], indent=1)[:900])
print("\nlicense_classification_rules:")
for r in prov["license_classification_rules"]:
    print("  -", r if isinstance(r, str) else json.dumps(r)[:200])

print("\n=== ANCHOR ROWS ===")
hits = 0
for i, x in enumerate(anchor, start=65):
    pn = by_id.get(x["id"], [])
    if pn:
        hits += 1
    print(f"\n[{i}] {x['id']}  fam={x['family']}  cls={x['classification']}")
    print(f"     name       : {x['name']}")
    print(f"     origin     : {x['origin']}")
    print(f"     provenance : {x['provenance']}")
    print(f"     license    : {x['license']}")
    print(f"     maintenance: {x['maintenance']}")
    print(f"     runtime    : {x['runtime']}")
    print(f"     does       : {x['does']}")
    print(f"     mechanisms : {x['mechanisms']}")
    print(f"     evidence   : {x['evidence']}")
    print(f"     notes      : {x['notes']}")
    print(f"     prov-graph : {len(pn)} node(s)")
    for n in pn[:2]:
        print("        ", json.dumps(n, ensure_ascii=False)[:700])

print(f"\nprov-graph id join: {hits}/{len(anchor)}")
