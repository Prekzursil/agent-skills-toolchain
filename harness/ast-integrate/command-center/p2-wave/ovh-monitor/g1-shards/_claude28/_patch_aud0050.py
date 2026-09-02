#!/usr/bin/env python3
"""shard-01 scratch: diff/patch AUD-0050 artifact against live mapper output."""
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes" / "AUD-0050"))
import mapper as M  # noqa: E402

live = M.compute(include_collection=False)
art_path = REPO / "command-center/audit/AUD-0050-test-gate-coverage-map.json"
doc = json.loads(art_path.read_text(encoding="utf-8"))

art_orphans = list(doc.get("orphan_list") or [])
live_orphans = live["orphan_list"]
art_map = {r["path"]: r["classification"] for r in (doc.get("gate_map") or []) if isinstance(r, dict) and r.get("path")}
live_map = {r["path"]: r["classification"] for r in live["gate_map"]}

print("orphans art", len(art_orphans), "live", len(live_orphans), "equal", art_orphans == live_orphans)
print("map art", len(art_map), "live", len(live_map), "equal", art_map == live_map)
only_art = [p for p in art_map if p not in live_map]
only_live = [p for p in live_map if p not in art_map]
diff_cls = [p for p in art_map if p in live_map and art_map[p] != live_map[p]]
print("map only_art", only_art[:10])
print("map only_live", only_live[:10])
print("map diff_cls", diff_cls[:10])
o_only_art = [p for p in art_orphans if p not in live_orphans]
o_only_live = [p for p in live_orphans if p not in art_orphans]
print("orph only_art", o_only_art[:10])
print("orph only_live", o_only_live[:10])
print("ctl", live["control"])
print("counts", live["n_test_files"], live["n_gated"], live["n_orphan"])

if len(sys.argv) > 1 and sys.argv[1] == "--write":
    doc["orphan_list"] = live["orphan_list"]
    doc["gate_map"] = live["gate_map"]
    for k in ("n_test_files", "n_gated", "n_orphan"):
        if k in doc:
            doc[k] = live[k]
    art_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("WROTE artifact")
