import hashlib, json, sys
from pathlib import Path
import jsonschema

REPO = Path.home() / "p2-g1"
IDS = ["IMP-0430","IMP-0435","IMP-0437","IMP-0439","IMP-0442","IMP-0448","IMP-0450","IMP-0460","IMP-0466","IMP-0467","IMP-0468","IMP-0470"]

def norm_sha(p):
    b = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest()

cat = json.loads((REPO/"command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = {u["id"]: u for u in cat["work_units"]}
results = {}

for uid in IDS:
    rep = {"checks": {}}
    entry = units.get(uid)
    rep["checks"]["catalog_entry"] = bool(entry)
    if not entry:
        results[uid] = rep; continue
    out_rel = entry["output_path"]; schema_rel = entry["output_schema"]
    rep["output_path"] = out_rel; rep["output_schema"] = schema_rel
    out_path = REPO / out_rel
    exists = out_path.is_file()
    size = out_path.stat().st_size if exists else 0
    rep["checks"]["artifact_exists"] = exists
    rep["checks"]["artifact_nonempty"] = size > 0
    rep["bytes"] = size
    parsed = None
    try:
        parsed = json.loads(out_path.read_text(encoding="utf-8"))
        rep["checks"]["artifact_parses"] = True
    except Exception as e:
        rep["checks"]["artifact_parses"] = False
        rep["parse_error"] = str(e)[:200]
    st = (parsed or {}).get("state")
    rep["state"] = st
    rep["checks"]["not_self_blocked"] = st not in ("BLOCKED", "FAILED")
    sent = (parsed or {}).get("sentinel") or ""
    csent = (parsed or {}).get("completion_sentinel") or ""
    rep["checks"]["no_failed_sentinel"] = not ("FAILED:" in sent or "FAILED:" in csent)
    rv = (parsed or {}).get("reviewer") or {}
    rep["reviewer"] = {k: rv.get(k) for k in ("verdict","independent","fresh_context","reviewer_id")}
    try:
        schema = json.loads((REPO/schema_rel).read_text(encoding="utf-8"))
        V = jsonschema.validators.validator_for(schema)
        V.check_schema(schema)
        errs = sorted(V(schema).iter_errors(parsed), key=lambda e: list(map(str, e.path)))
        rep["checks"]["schema_valid"] = not errs
        if errs:
            rep["schema_errors"] = [f"{list(map(str,e.path))}: {e.message[:160]}" for e in errs[:5]]
    except Exception as e:
        rep["checks"]["schema_valid"] = False
        rep["schema_errors"] = ["schema-load: " + str(e)[:200]]
    man_p = REPO / ("command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json" % uid)
    try:
        man = json.loads(man_p.read_text(encoding="utf-8"))
        rows = man.get("artifacts", [])
        live = norm_sha(out_path)
        rep["live_sha256_lf"] = live
        mine = [r for r in rows if r.get("path") == out_rel]
        rep["checks"]["manifest_row_present"] = bool(mine)
        if mine:
            rep["manifest_sha256"] = mine[0].get("sha256")
            rep["checks"]["manifest_sha_match"] = mine[0].get("sha256") == live
        mism = []
        for r in rows:
            p2 = REPO / r.get("path","")
            if r.get("path") != out_rel and p2.is_file():
                if norm_sha(p2) != r.get("sha256"):
                    mism.append(r.get("path"))
        rep["manifest_other_rows_mismatch"] = mism
    except Exception as e:
        rep["checks"]["manifest_row_present"] = False
        rep["manifest_error"] = str(e)[:200]
    allc = rep["checks"]
    rep["STATIC_OK"] = all(allc.values()) and not rep.get("manifest_other_rows_mismatch")
    results[uid] = rep

out = REPO/"_p2shard14-w3-review/r2-static-results.json"
out.write_text(json.dumps(results, indent=1), encoding="utf-8")
for uid in IDS:
    r = results[uid]
    print(uid, "STATIC_OK" if r.get("STATIC_OK") else "FAIL", json.dumps(r["checks"]))
    for k in ("schema_errors","manifest_error","parse_error"):
        if r.get(k): print("   ", k, r[k][:200])
    if r.get("manifest_other_rows_mismatch"): print("    other-row-mismatch:", r["manifest_other_rows_mismatch"])
    if not r["checks"].get("manifest_sha_match", True): print("    live:", r.get("live_sha256_lf"), "manifest:", r.get("manifest_sha256"))
