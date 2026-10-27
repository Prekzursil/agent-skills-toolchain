#!/usr/bin/env python3
"""Is my 1,045 'dangling dependency ref' count a FINDING or a DETECTOR ARTIFACT?

The brief asserts 41 unresolvable dependency refs. My frontier probe said 1,045 across 794
units. Before citing either, resolve the dangling refs against EVERY namespace the catalog
actually declares (work_units ids, items[] register ids, bucket/phase ids, defaults).

Terminal state: SUCCESS:gwlazy-depns / FAILED:gwlazy-depns <reason>
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = REPO / "platform" / "architecture" / "_probe_gwlazy_depns_out.json"
res: dict = {"probe": "gwlazy-depns"}

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
wus = cat["work_units"]

unit_ids = {str(w.get("id")) for w in wus if w.get("id")}
res["namespaces"] = {"work_unit_ids": len(unit_ids)}

# items[] register
items = cat.get("items") or []
item_ids = set()
for it in items:
    for k in ("id", "item_id", "key", "name"):
        if isinstance(it, dict) and it.get(k):
            item_ids.add(str(it[k]))
res["namespaces"]["items_ids"] = len(item_ids)
res["items_id_samples"] = sorted(item_ids)[:20]

# any bucket / band table anywhere in the catalog top level
other_ns = {}
for k, v in cat.items():
    if k in ("work_units",):
        continue
    blob = json.dumps(v)
    for pat, label in ((r"\bB\d{2}\b", "Bnn"), (r"\bP\d{2}\b", "Pnn")):
        hits = set(re.findall(pat, blob))
        if hits:
            other_ns.setdefault(label, {})[k] = sorted(hits)
res["Bnn_Pnn_tokens_by_top_level_key"] = {
    lab: {k: len(v) for k, v in d.items()} for lab, d in other_ns.items()
}

# every declared dep, classified
deps_all = Counter()
per_unit_unresolved = {}
for w in wus:
    i = str(w.get("id"))
    ds = w.get("dependencies") or []
    if isinstance(ds, str):
        ds = [ds]
    bad = []
    for d in ds:
        d = str(d)
        deps_all[d] += 1
        if d not in unit_ids:
            bad.append(d)
    if bad:
        per_unit_unresolved[i] = bad

flat = [d for v in per_unit_unresolved.values() for d in v]
res["dep_refs_total"] = sum(deps_all.values())
res["dep_refs_distinct"] = len(deps_all)
res["unresolved_vs_work_unit_ids"] = {
    "refs": len(flat),
    "distinct": len(set(flat)),
    "units_affected": len(per_unit_unresolved),
    "distinct_tokens": sorted(set(flat)),
}

# now resolve those distinct tokens against the other namespaces
tokens = set(flat)
res["resolution_of_unresolved_tokens"] = {
    "in_items_ids": sorted(tokens & item_ids),
    "match_Bnn_shape": sorted(t for t in tokens if re.fullmatch(r"B\d{2}", t)),
    "match_bucket_word": sorted(t for t in tokens if "bucket" in t.lower()),
    "match_phase_shape": sorted(t for t in tokens if re.fullmatch(r"(?:P|PH|phase)[-_]?\d+[A-Z]?", t, re.I)),
    "remaining_unexplained": sorted(
        t for t in tokens
        if t not in item_ids and not re.fullmatch(r"B\d{2}", t) and "bucket" not in t.lower()
    ),
}

# does a bucket namespace exist ANYWHERE in the repo for those tokens?
bshape = sorted(t for t in tokens if re.fullmatch(r"B\d{2}", t))
res["bucket_namespace_search"] = {}
if bshape:
    probe = bshape[0]
    hits = []
    for p in (REPO / "command-center").rglob("*.json"):
        if p.name == "WORK-UNIT-CATALOG.json":
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if re.search(rf'"{probe}"', t):
            hits.append(str(p.relative_to(REPO)).replace("\\", "/"))
    res["bucket_namespace_search"] = {
        "probe_token": probe,
        "files_declaring_it_as_a_json_string": hits[:15],
        "n_files": len(hits),
    }
    # detector control: a token that certainly does not exist
    ghost = "B99ZZZ"
    gh = [
        str(p.relative_to(REPO)).replace("\\", "/")
        for p in (REPO / "command-center").rglob("*.json")
        if re.search(rf'"{ghost}"', p.read_text(encoding="utf-8", errors="replace"))
    ]
    res["bucket_namespace_search"]["detector_control_ghost_token_hits"] = len(gh)
    res["bucket_namespace_search"]["detector_valid"] = len(gh) == 0

# also: how many units declare deps at all
res["units_declaring_deps"] = sum(1 for w in wus if (w.get("dependencies") or []))
res["units_declaring_zero_deps"] = len(wus) - res["units_declaring_deps"]

OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
p = dict(res)
p["unresolved_vs_work_unit_ids"] = {
    k: (v if k != "distinct_tokens" else v[:40]) for k, v in res["unresolved_vs_work_unit_ids"].items()
}
print(json.dumps(p, indent=2)[:6000])
print(f"\nwrote {OUT}")
print("SUCCESS:gwlazy-depns")
