"""WFA-2of2 grounding probe.

Recount every fact the slice cites DIRECTLY FROM THE ARRAYS, never from the
self-declared `counts` blocks (a counts block is the same signal as the doc's
own prose; recounting the arrays is the mechanically different second probe).

Also runs a detector control: a sentinel that must be found (known-present) and
a sentinel that must NOT be found (known-absent).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

CORPUS = Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806")

out: dict[str, object] = {}

# ---- 08 candidate registry -------------------------------------------------
reg = json.loads((CORPUS / "08-WORKFLOW-CANDIDATE-REGISTRY.json").read_text(encoding="utf-8"))
cands = reg["candidates"]
vocab = reg["classification_vocabulary"]
cls = Counter(c["classification"] for c in cands)
out["candidates_recounted"] = len(cands)
out["candidates_declared"] = reg["counts"]["total"]
out["families_recounted"] = dict(Counter(c["family"] for c in cands))
out["classification_recounted"] = dict(cls)
out["vocab_size"] = len(vocab)
out["vocab_values_never_assigned"] = sorted(v for v in vocab if cls.get(v, 0) == 0)
out["unknown_needs_probe_recounted"] = cls.get("UNKNOWN-NEEDS-PROBE", 0)
out["candidate_ids_unique"] = len({c["id"] for c in cands}) == len(cands)

# ---- 08 provenance / license graph ----------------------------------------
prov = json.loads((CORPUS / "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json").read_text(encoding="utf-8"))
out["prov_nodes_recounted"] = len(prov["nodes"])
out["prov_edges_recounted"] = len(prov["edges"])
out["license_risk_rows_recounted"] = len(prov["license_risk_register"])
out["license_rules_recounted"] = len(prov["license_classification_rules"])
out["prov_finding_keys"] = list(prov["FINDING_unresolved_provenance"].keys())
out["prov_discovery_only"] = prov.get("discovery_only")

# ---- 09 blueprint library --------------------------------------------------
bp = json.loads((CORPUS / "09-WORKFLOW-BLUEPRINT-LIBRARY.json").read_text(encoding="utf-8"))
bps = bp["blueprints"]
out["blueprints_recounted"] = len(bps)
out["blueprint_families_recounted"] = len({b["fam"] for b in bps})
out["blueprint_routes_recounted"] = dict(Counter(b["route"] for b in bps))
out["blueprint_field_schema_len"] = len(bp["field_schema"])
out["blueprint_discovery_only"] = bp.get("discovery_only")
out["blueprint_states_recounted"] = dict(Counter(b.get("state") for b in bps))

# ---- 10 merge / composition maps ------------------------------------------
mg = json.loads((CORPUS / "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json").read_text(encoding="utf-8"))
out["merge_units_recounted"] = len(mg["merge_units"])
out["conflict_rows_recounted"] = len(mg["conflict_map"])
out["external_deps_recounted"] = len(mg["external_dependency_map"])
out["family_matrix_rows_recounted"] = len(mg["family_composition_matrix"])
out["merge_declared_counts"] = mg["counts"]

# Recompute the asymmetry from the blueprint `compat` field itself, not from
# the merge doc's counts block -- an independent derivation of the same number.
compat: dict[str, set[str]] = {}
for b in bps:
    raw = b.get("compat") or []
    if isinstance(raw, str):
        raw = [t.strip() for t in raw.split(",") if t.strip()]
    compat[b["id"]] = {str(t).strip() for t in raw if str(t).strip()}
declared = sum(len(v) for v in compat.values())
asym = 0
undirected: set[frozenset[str]] = set()
dangling = 0
for src, targets in compat.items():
    for tgt in targets:
        if tgt not in compat:
            dangling += 1
            continue
        undirected.add(frozenset((src, tgt)))
        if src not in compat[tgt]:
            asym += 1
out["compat_declared_refs_rederived"] = declared
out["compat_undirected_edges_rederived"] = len(undirected)
out["compat_asymmetric_rederived"] = asym
out["compat_dangling_rederived"] = dangling

# ---- detector control ------------------------------------------------------
# known-present: 'ADOPT-AS-IS' is in the vocabulary and IS assigned.
# known-absent : a sentinel string that cannot occur in either corpus.
blob = json.dumps(reg) + json.dumps(bp)
out["control_known_present_hits"] = blob.count("ADOPT-AS-IS")
out["control_known_absent_hits"] = blob.count("ZZZ-WFA2-SENTINEL-NOT-PRESENT")
out["detector_control_pass"] = bool(
    out["control_known_present_hits"] > 0 and out["control_known_absent_hits"] == 0
)

print(json.dumps(out, indent=1, sort_keys=True))
