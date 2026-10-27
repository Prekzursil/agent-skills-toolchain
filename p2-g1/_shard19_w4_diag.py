
import json, sys
sys.path.insert(0, "platform/lib")
import schema_resolver as sr
import importlib.util
spec = importlib.util.spec_from_file_location("gate", "platform/lib/receipt_schema_gate.py")
gate = importlib.util.module_from_spec(spec); sys.modules["gate"]=gate; spec.loader.exec_module(gate)

def gv(x):
    return x if isinstance(x, dict) else {}

units = ["TST-0168","TST-0169","TST-0171","TST-0174","TST-0195","TST-0197","TST-0202","TST-0204","TST-0206","TST-0215","TST-0219","TST-0221"]
cat = json.load(open("command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"] if u.get("id") in units}
out = {}
for uid in units:
    ref = byid[uid]["output_schema"]
    doc = json.load(open(f"command-center/receipts/{uid}.json", encoding="utf-8"))
    r_errs = sr.validate_artifact(doc, ref)
    g_errs = gate.validate_receipt(doc)
    ev = doc.get("evidence")
    ev_shape = []
    if isinstance(ev, list):
        for e in ev[:4]:
            e = gv(e)
            p = e.get("probes")
            ev_shape.append({"claim": str(e.get("claim"))[:80], "verdict": e.get("verdict"), "confidence": e.get("confidence"), "anchor": bool(e.get("anchor")), "probes": (len(p) if isinstance(p, list) else str(type(p).__name__)), "probe_roles": [gv(q).get("role") for q in p if isinstance(q, dict)] if isinstance(p, list) else None})
    elif isinstance(ev, str):
        ev_shape = [{"raw_str": ev[:100]}]
    else:
        ev_shape = str(type(ev).__name__)
    arts = doc.get("artifacts")
    art_rows = []
    if isinstance(arts, list):
        for a in arts[:8]:
            if not isinstance(a, dict):
                art_rows.append({"raw": str(a)[:60]}); continue
            art_rows.append({"path": str(a.get("path") or a.get("artifact_path") or "?")[:70], "role": a.get("role"), "exists": a.get("exists"), "has_bytes": "bytes" in a, "has_sha": "sha256" in a, "extra": sorted(set(a.keys()) - {"path","bytes","sha256","exists","eol","role"})[:6]})
    t = doc.get("tests")
    if isinstance(t, list):
        tres = sorted(set(str(x.get("result")) for x in t if isinstance(x, dict)))
    else:
        tres = str(type(t).__name__)
    ncs = doc.get("negative_controls")
    nc_rows = []
    if isinstance(ncs, list):
        for nc in ncs[:6]:
            if not isinstance(nc, dict): continue
            nc_rows.append([nc.get("id"), nc.get("kind"), nc.get("fired_on_bad_state"), nc.get("silent_on_good_state")])
    dcs = doc.get("downstream_consumers")
    dc_rows = []
    if isinstance(dcs, list):
        for d in dcs[:4]:
            if not isinstance(d, dict): continue
            dc_rows.append([str(d.get("consumer"))[:40], d.get("executed"), d.get("read_ok"), d.get("exit_code"), "probe" in d])
    reps = doc.get("defects")
    def_rows = []
    if isinstance(reps, list):
        for d in reps[:8]:
            if not isinstance(d, dict): continue
            def_rows.append([d.get("id"), d.get("severity"), d.get("status")])
    rep = doc.get("report")
    if isinstance(rep, dict):
        rep_info = (sorted(rep.keys())[:8], len(rep.get("observations") or []), bool(rep.get("control_ids")))
    else:
        rep_info = (str(type(rep).__name__), None, None)
    info = {
        "state": doc.get("state"),
        "sentinel": str(doc.get("sentinel"))[:250],
        "n_resolver_errors": len(r_errs),
        "resolver_errors": [e[:180] for e in r_errs],
        "n_gate_errors": len(g_errs),
        "gate_errors": [e[:180] for e in g_errs],
        "missing_core": [k for k in ("downstream_consumers","manifest_registration","residual_unknowns","retry","min_bytes_threshold","timestamps","artifacts","evidence","tests","negative_controls","report","spec_anchor","schema_version","produced_by") if k not in doc],
        "evidence": ev_shape,
        "tests_results": tres,
        "nc": nc_rows,
        "artifacts": art_rows,
        "dc": dc_rows,
        "mr": doc.get("manifest_registration"),
        "defects": def_rows,
        "timestamps": doc.get("timestamps"),
        "retry": bool(doc.get("retry")),
        "mbt": doc.get("min_bytes_threshold"),
        "report": rep_info,
        "schema_version": doc.get("schema_version"),
        "spec_anchor": str(doc.get("spec_anchor"))[:60],
        "produced_by": bool(doc.get("produced_by")),
        "reviewer": sorted((doc.get("reviewer") or {}).keys()) if isinstance(doc.get("reviewer"), dict) else str(type(doc.get("reviewer")).__name__),
    }
    out[uid] = info
with open("_shard19_w4_diag.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=True, indent=1)
print("WROTE _shard19_w4_diag.json")
