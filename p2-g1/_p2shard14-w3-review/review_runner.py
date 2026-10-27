import json, hashlib, subprocess, sys, os, glob, traceback
from pathlib import Path

ROOT = Path(r"C:\Users\Prekzursil\p2-g1")
IDS = ["IMP-0430","IMP-0435","IMP-0437","IMP-0439","IMP-0442","IMP-0448",
       "IMP-0450","IMP-0460","IMP-0466","IMP-0467","IMP-0468","IMP-0470"]
OUTDIR = ROOT / "_p2shard14-w3-review" / "logs"
OUTDIR.mkdir(parents=True, exist_ok=True)

cat = json.loads((ROOT / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = {u["id"]: u for u in cat["work_units"]}

def norm_sha(p):
    b = p.read_bytes()
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from urllib.parse import unquote, urlparse

def retrieve(uri):
    path = unquote(urlparse(uri).path).lstrip("/")
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return Resource.from_contents(doc, default_specification=DRAFT202012)

registry = Registry(retrieve=retrieve)

def build_validator(shim_path):
    shim = json.loads(shim_path.read_text(encoding="utf-8"))
    ref = shim["$ref"]
    base, frag = ref.split("#", 1)
    phys_path = ROOT / unquote(urlparse(base).path).lstrip("/").split("source/ast-integrate/")[-1]
    phys = json.loads(phys_path.read_text(encoding="utf-8"))
    res = Resource.from_contents(phys, default_specification=DRAFT202012)
    reg = registry.with_resource(uri=base, resource=res)
    node = phys
    for part in frag.lstrip("/").split("/"):
        node = node[part]
    return Draft202012Validator(node, registry=reg)

results = {}
for uid in IDS:
    r = {"id": uid}
    ce = units[uid]
    r["catalog_output_path"] = ce.get("output_path")
    r["catalog_schema"] = ce.get("output_schema")
    r["catalog_sentinel"] = ce.get("completion_sentinel")
    out_rel = ce["output_path"]
    art = ROOT / out_rel
    r["exists"] = art.exists()
    r["bytes_raw"] = art.stat().st_size if art.exists() else 0
    if not art.exists() or r["bytes_raw"] == 0:
        r["FAIL"] = "artifact missing or empty at catalog output_path"
        results[uid] = r; continue
    try:
        receipt = json.loads(art.read_text(encoding="utf-8"))
        r["parses"] = True
    except Exception as e:
        r["parses"] = False; r["FAIL"] = "artifact does not parse: %s" % e
        results[uid] = r; continue
    r["state"] = receipt.get("state")
    if r["state"] in ("BLOCKED", "FAILED"):
        r["FAIL"] = "self-declared state=%s" % r["state"]
        results[uid] = r; continue
    pre = norm_sha(art)
    pdir = ROOT / "command-center" / "p2-wave" / "probes" / uid
    probes = sorted(pdir.glob("probe*.py"))
    r["probes"] = []
    probe_ok = True
    for p in probes:
        logf = OUTDIR / ("%s_%s.log" % (uid, p.stem))
        try:
            cp = subprocess.run([sys.executable, str(p)], cwd=str(pdir),
                                capture_output=True, text=True, timeout=600)
            rc, out, err = cp.returncode, cp.stdout, cp.stderr
        except subprocess.TimeoutExpired:
            rc, out, err = "TIMEOUT", "", "probe timed out after 600s"
        logf.write_text("=== %s rc=%s\n--- stdout ---\n%s\n--- stderr ---\n%s" % (p.name, rc, out, err), encoding="utf-8")
        r["probes"].append({"probe": p.name, "rc": rc})
        if rc != 0:
            probe_ok = False
    r["probes_ok"] = probe_ok
    post = norm_sha(art)
    r["sha_pre"] = pre; r["sha_post"] = post
    r["artifact_mutated_by_probes"] = (pre != post)
    mf = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    r["manifest_present"] = mf.exists()
    if mf.exists():
        try:
            man = json.loads(mf.read_text(encoding="utf-8"))
            rows = [a for a in man.get("artifacts", []) if a.get("path") == out_rel]
            r["manifest_rows"] = len(rows)
            if not rows:
                r["manifest_match"] = None
            else:
                row = rows[0]
                r["manifest_sha"] = row.get("sha256")
                r["manifest_match"] = (row.get("sha256") == post)
                r["manifest_bytes"] = row.get("bytes")
                r["manifest_receipt_state"] = man.get("receipt_state")
        except Exception as e:
            r["manifest_match"] = None; r["FAIL_manifest"] = str(e)
    else:
        r["manifest_match"] = None
    shim_rel = ce.get("output_schema")
    try:
        v = build_validator(ROOT / shim_rel)
        errs = sorted(v.iter_errors(receipt), key=lambda e: list(map(str, e.path)))
        r["schema_errors"] = ["%s: %s" % (list(e.path), e.message[:300]) for e in errs[:8]]
        r["schema_ok"] = (len(errs) == 0)
        r["schema_error_count"] = len(errs)
    except Exception as e:
        r["schema_ok"] = None; r["schema_errors"] = ["validator-build error: %s" % e]
    rev = receipt.get("reviewer") or {}
    r["reviewer_verdict"] = rev.get("verdict")
    r["reviewer_independent"] = rev.get("independent")
    r["reviewer_id"] = rev.get("reviewer_id")
    r["receipt_sentinel"] = receipt.get("sentinel") or receipt.get("completion_sentinel")
    r["sentinel_matches_catalog"] = (r["receipt_sentinel"] == r["catalog_sentinel"])
    results[uid] = r

(ROOT / "_p2shard14-w3-review" / "results.json").write_text(
    json.dumps(results, indent=1), encoding="utf-8")

for uid, r in results.items():
    print("==", uid)
    for k in ["exists","bytes_raw","parses","state","probes_ok","manifest_match",
              "schema_ok","schema_error_count","reviewer_verdict",
              "reviewer_independent","reviewer_id","sentinel_matches_catalog","artifact_mutated_by_probes"]:
        print("  ", k, "=", r.get(k))
    if r.get("probes"):
        print("   probes:", [(p["probe"], p["rc"]) for p in r["probes"]])
    for se in (r.get("schema_errors") or [])[:4]: print("    SCHEMA-ERR:", se)
    if r.get("FAIL"): print("    FAIL:", r["FAIL"])
