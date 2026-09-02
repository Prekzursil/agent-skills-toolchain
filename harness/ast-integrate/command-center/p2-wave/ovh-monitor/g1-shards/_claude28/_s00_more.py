#!/usr/bin/env python3
"""Small remaining dumps. Not a measurement."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")


def load(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))

d = load("command-center/confirmation/CNF-0029-change-surface.json")
br = (d.get("report") or {}).get("branches") or []
for b in br:
    print("BRANCH", b.get("name"), "keys", sorted(b.keys()))
    for k in ("three_dot", "two_dot"):
        v = b.get(k)
        print(" ", k, type(v).__name__, (sorted(v.keys()) if isinstance(v, dict) else v) )

d = load("command-center/wfa/WFA-0025-sweep-academic-protocols.json")
for src in ("top", "legacy"):
    prots = d.get("protocols") if src == "top" else ((d.get("extensions") or {}).get("legacy_root") or {}).get("protocols")
    print("WFA-0025", src, "n", len(prots or []))
    for p in prots or []:
        est = p.get("estate") or {}
        print(" ", p.get("protocol_id") or p.get("id"), est.get("status"), est.get("implementing_candidate_id"))

d = load("command-center/design/council/CNL-0118-role-enforcement-and-participant-replacement-simulation.md")
for t in d.get("tests") or []:
    if t.get("id") in {"probe1-replay", "probe2-recount"}:
        print("CNL-0118", t.get("id"), t.get("result"), t.get("command"))

# IMP-0200 corpus
import sys
sys.path.insert(0, str(REPO / "command-center"))
from workflow_tournament import matched_corpus  # noqa: E402
c = matched_corpus()
print("IMP-0200 live corpus n", len(c), [x.get("id") or x.get("workflow_id") for x in c])

d = load("command-center/foundry/WFA-0153-close-the-unresolved-nodes-in-the-466-node-provenanc.json")
print("WFA-0153 top survivors", len(d.get("survivors") or []))
leg = (d.get("extensions") or {}).get("legacy_root") or {}
print("WFA-0153 legacy survivors", len(leg.get("survivors") or []))
print("WFA-0153 name_not_evidence", d.get("name_not_evidence") or leg.get("name_not_evidence"))
print("WFA-0153 graph", d.get("graph") or leg.get("graph"))
finding = d.get("finding_unresolved_provenance") or leg.get("finding_unresolved_provenance") or {}
print("WFA-0153 finding refs", len(finding.get("unresolved_refs") or []), "probe", bool(finding.get("settling_probe")))

# CNF-0145 SUBAGENT
ret = json.loads((REPO / "command-center/p2-wave/probes/CNF-0145/SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
print("CNF-0145 ret keys", sorted(ret.keys())[:20])
raw = (ret.get("named_probes") or [{}])[0].get("raw_output") or ""
print("CNF-0145 p1 raw tail", raw[-400:])
