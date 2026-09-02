#!/usr/bin/env python3
"""The lazy-activation lever on the EXECUTION plane: how many of the 2,007 units must be
resident at once if the gateway admits only the ready frontier?

Topologically layer work_units by their declared `dependencies`, measure the frontier width
per layer, and compare peak-resident bytes against eager-resident bytes (whole catalog).

Detector control: a synthetic 3-unit chain must produce widths [1,1,1]; a synthetic 3-unit
fan must produce [3]. A layerer that returns the same shape for both measures nothing.

Terminal state: SUCCESS:gwlazy-frontier / FAILED:gwlazy-frontier <reason>
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = REPO / "platform" / "architecture" / "_probe_gwlazy_frontier_out.json"
res: dict = {"probe": "gwlazy-frontier"}


def layer(nodes: dict) -> tuple[list, dict]:
    """nodes: id -> list of dep ids. Returns (widths, diag). Unresolvable deps are dropped
    (recorded), which is the permissive reading; the strict reading is reported too."""
    known = set(nodes)
    dangling = defaultdict(list)
    indeg = {}
    children = defaultdict(list)
    for n, deps in nodes.items():
        real = []
        for d in deps or []:
            if d in known:
                real.append(d)
            else:
                dangling[n].append(d)
        indeg[n] = len(real)
        for d in real:
            children[d].append(n)
    widths = []
    ready = sorted(n for n, k in indeg.items() if k == 0)
    seen = 0
    while ready:
        widths.append(len(ready))
        seen += len(ready)
        nxt = []
        for n in ready:
            for c in children[n]:
                indeg[c] -= 1
                if indeg[c] == 0:
                    nxt.append(c)
        ready = sorted(nxt)
    diag = {
        "nodes": len(nodes),
        "layered": seen,
        "unlayered_cycle_or_stuck": len(nodes) - seen,
        "units_with_dangling_dep": len(dangling),
        "dangling_dep_refs": sum(len(v) for v in dangling.values()),
        "dangling_samples": {k: v for k, v in list(dangling.items())[:5]},
    }
    return widths, diag


# ---------------- detector control (both shapes) ----------------
chain_w, _ = layer({"a": [], "b": ["a"], "c": ["b"]})
fan_w, _ = layer({"a": [], "b": [], "c": []})
dangle_w, dangle_d = layer({"a": ["ghost"], "b": ["a"]})
ctl = {
    "chain_widths": chain_w,
    "fan_widths": fan_w,
    "chain_expected": [1, 1, 1],
    "fan_expected": [3],
    "dangling_detected": dangle_d["dangling_dep_refs"],
    "dangling_expected": 1,
}
ctl["detector_valid"] = (
    chain_w == [1, 1, 1] and fan_w == [3] and dangle_d["dangling_dep_refs"] == 1
)
res["detector_control"] = ctl

# ---------------- real catalog ----------------
cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
wus = cat["work_units"]


def uid(w):
    for k in ("id", "unit_id", "ID"):
        if w.get(k):
            return str(w[k])
    return None


ids = [uid(w) for w in wus]
res["units_with_no_id"] = sum(1 for i in ids if not i)
res["duplicate_ids"] = len(ids) - len(set(i for i in ids if i))

nodes = {}
sizes = {}
for w in wus:
    i = uid(w)
    if not i:
        continue
    deps = w.get("dependencies") or []
    if isinstance(deps, str):
        deps = [deps]
    nodes[i] = [str(x) for x in deps if isinstance(x, (str, int))]
    sizes[i] = len(json.dumps(w).encode())

widths, diag = layer(nodes)
res["diag"] = diag
res["layers"] = len(widths)
res["frontier_widths"] = widths
res["frontier_width_max"] = max(widths) if widths else 0
res["frontier_width_mean"] = round(sum(widths) / max(1, len(widths)), 1)

# resident-bytes comparison
mean_sz = sum(sizes.values()) // max(1, len(sizes))
res["unit_bytes_mean"] = mean_sz
res["eager_resident_bytes_whole_catalog"] = (REPO / "command-center/WORK-UNIT-CATALOG.json").stat().st_size
res["lazy_peak_resident_bytes_widest_layer"] = res["frontier_width_max"] * mean_sz
res["lazy_reduction_factor"] = round(
    res["eager_resident_bytes_whole_catalog"] / max(1, res["lazy_peak_resident_bytes_widest_layer"]), 1
)

# concurrency reality: the widest layer is NOT the concurrency the box can take
res["substrate_of_widest_layer"] = None
if widths:
    # rebuild layer 0..n to name the widest layer's substrate mix
    known = set(nodes)
    indeg = {n: len([d for d in deps if d in known]) for n, deps in nodes.items()}
    children = defaultdict(list)
    for n, deps in nodes.items():
        for d in deps:
            if d in known:
                children[d].append(n)
    by_id = {uid(w): w for w in wus if uid(w)}
    ready = sorted(n for n, k in indeg.items() if k == 0)
    best = (0, -1, [])
    li = 0
    while ready:
        if len(ready) > best[0]:
            best = (len(ready), li, list(ready))
        nxt = []
        for n in ready:
            for c in children[n]:
                indeg[c] -= 1
                if indeg[c] == 0:
                    nxt.append(c)
        ready = sorted(nxt)
        li += 1
    from collections import Counter

    res["widest_layer_index"] = best[1]
    res["widest_layer_substrates"] = dict(
        Counter(str(by_id[i].get("execution_substrate")) for i in best[2]).most_common()
    )
    res["widest_layer_phases"] = dict(
        Counter(str(by_id[i].get("phase")) for i in best[2]).most_common(8)
    )

OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
printable = {k: v for k, v in res.items() if k != "frontier_widths"}
printable["frontier_widths_first25"] = res["frontier_widths"][:25]
print(json.dumps(printable, indent=2))
print(f"\nwrote {OUT}")
print("SUCCESS:gwlazy-frontier" if ctl["detector_valid"] else "FAILED:gwlazy-frontier detector-control-failed")
