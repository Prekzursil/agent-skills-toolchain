import hashlib, json, os
from pathlib import Path

REPO = Path.home() / "p2-g1"
ready = json.loads((REPO / "command-center" / "READY-UNITS.json").read_text(encoding="utf-8"))
ids = ready["ready_units"]

def shard(uid):
    return int(hashlib.sha256(uid.encode("utf-8")).hexdigest(), 16) % 6

mine = [u for u in ids if shard(u) == 0]
print("total_ready", len(ids))
print("my_filter_total", len(mine))
wave = mine[:15]
print("wave_a", json.dumps(wave))

cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
by_id = {}
for u in cat.get("work_units") or []:
    if isinstance(u, dict) and isinstance(u.get("id"), str):
        by_id[u["id"]] = u

out = {}
for uid in wave:
    u = by_id.get(uid)
    if u is None:
        out[uid] = {"catalog": "MISSING"}
        continue
    pd = REPO / "command-center" / "p2-wave" / "probes" / uid
    probe_files = sorted(p.name for p in pd.iterdir()) if pd.is_dir() else []
    keep = {k: u.get(k) for k in ("id", "title", "description", "output_path", "output_schema",
                                   "named_probes", "probes", "dependencies", "completion_sentinel",
                                   "contract", "acceptance", "bucket", "wave", "status")
            if k in u}
    out[uid] = {"catalog": keep, "probe_files": probe_files,
                "extra_catalog_keys": sorted(set(u.keys()) - set(keep.keys()))}

dest = Path("/tmp/s0_shardA.json")
dest.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
print("wrote", dest)
# also print distribution for sanity
from collections import Counter
print("distribution", dict(Counter(shard(u) for u in ids)))
