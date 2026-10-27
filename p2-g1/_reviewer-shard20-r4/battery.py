#!/usr/bin/env python3
"""Independent reviewer battery, wave-2 shard 20 (12 units).
Re-verifies EVERYTHING off disk; trusts no prior claim."""
import hashlib, json, subprocess, sys, os
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
UNITS = ["RES-0184","RES-0185","RES-0187","RES-0188","RES-0191",
         "RES-0192","RES-0193","SYN-0003","SYN-0007","SYN-0008","SYN-0035","TST-0005"]

cat = json.loads((REPO/"command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
entries = {u["id"]: u for u in cat["work_units"]}

def norm_sha(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

def raw_sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def find_self_block(doc, path="$", hits=None, depth=0):
    if hits is None: hits = []
    if depth > 3: return hits
    if isinstance(doc, dict):
        for k, v in doc.items():
            if k.lower() in ("state","status","sentinel","verdict","result") and isinstance(v,str):
                up = v.upper()
                if up.startswith("BLOCKED") or up.startswith("FAILED"):
                    hits.append((path+"."+k, v[:80]))
            if isinstance(v,(dict,list)):
                find_self_block(v, path+"."+k, hits, depth+1)
    elif isinstance(doc, list):
        for i, v in enumerate(doc[:50]):
            if isinstance(v,(dict,list)):
                find_self_block(v, path+"[%d]"%i, hits, depth+1)
    return hits

results = {}
for uid in UNITS:
    e = entries.get(uid)
    r = {"unit": uid, "checks": [], "fail": None}
    def chk(name, ok, detail=""):
        r["checks"].append((name, bool(ok), detail))
        if not ok: r["fail"] = r["fail"] or (name + ": " + str(detail))
        return ok

    if e is None:
        chk("catalog-entry", False, "no catalog entry"); results[uid]=r; continue
    out_rel = e.get("output_path"); sch_rel = e.get("output_schema")
    out = REPO / out_rel
    chk("artifact-exists", out.is_file(), out_rel)
    if not out.is_file(): results[uid]=r; continue
    chk("artifact-nonempty", out.stat().st_size > 0, "%d bytes" % out.stat().st_size)
    try:
        doc = json.loads(out.read_text(encoding="utf-8")); chk("artifact-parses", True)
    except Exception as exc:
        chk("artifact-parses", False, repr(exc)); results[uid]=r; continue
    chk("state-not-blocked", str(doc.get("state","")).upper() not in ("BLOCKED","FAILED"),
        "state=%s" % doc.get("state"))
    hits = find_self_block(doc)
    top_hits = [h for h in hits if h[0].count(".") <= 1]
    chk("no-self-block-decl", not top_hits, "; ".join("%s=%s"%(a,b) for a,b in top_hits[:3]))
    sch = REPO / sch_rel
    if chk("schema-file-exists", sch.is_file(), sch_rel):
        try:
            import jsonschema
            schema = json.loads(sch.read_text(encoding="utf-8"))
            errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(doc),
                          key=lambda x: list(x.absolute_path))
            chk("schema-valid", not errs, errs[0].message[:200] if errs else "")
        except Exception as exc:
            chk("schema-valid", False, repr(exc)[:200])
    mf = REPO/("command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json" % uid)
    if chk("manifest-exists", mf.is_file(), str(mf)):
        try:
            man = json.loads(mf.read_text(encoding="utf-8"))
        except Exception as exc:
            chk("manifest-parses", False, repr(exc)); man=None
        if man is not None:
            rows = [a for a in man.get("artifacts",[]) if a.get("path","").replace("\\","/") == out_rel]
            chk("manifest-primary-row", len(rows)>=1, "%d rows for %s" % (len(rows), out_rel))
            if rows:
                row = rows[0]
                nsha, rsha = norm_sha(out), raw_sha(out)
                chk("manifest-sha-match(norm-CRLF2LF)", row.get("sha256")==nsha,
                    "manifest=%s.. norm=%s.. raw=%s.." % (row.get("sha256","")[:16], nsha[:16], rsha[:16]))
                r["bytes_field"] = row.get("bytes"); r["live_bytes"] = out.stat().st_size
            bad_rows = []
            for a in man.get("artifacts",[]):
                ap = REPO / a.get("path","")
                if not ap.is_file(): bad_rows.append((a["path"],"absent")); continue
                if norm_sha(ap) != a.get("sha256") and raw_sha(ap) != a.get("sha256"):
                    bad_rows.append((a["path"],"sha-mismatch"))
            r["other_rows_flag"] = bad_rows
    pdir = REPO/("command-center/p2-wave/probes/%s" % uid)
    probes = sorted(pdir.glob("probe*.py"))
    chk("probes-present", len(probes)>=1, "%d probe files" % len(probes))
    env = dict(os.environ); env["PYTHONDONTWRITEBYTECODE"]="1"
    for pb in probes:
        try:
            cp = subprocess.run([sys.executable, "-B", str(pb)], capture_output=True, text=True,
                                timeout=300, env=env, cwd=str(REPO))
        except Exception as exc:
            chk("probe:%s:run" % pb.name, False, repr(exc)[:150]); continue
        outp = (cp.stdout or "").strip().splitlines()
        okline = any(l.startswith("PROBE-OK") for l in outp)
        chk("probe:%s:exit0" % pb.name, cp.returncode==0,
            "rc=%d tail=%s" % (cp.returncode, (cp.stdout or cp.stderr).strip()[-160:]))
        if cp.returncode==0:
            chk("probe:%s:PROBE-OK-line" % pb.name, okline,
                "tail=%s" % (outp[-1][:100] if outp else "<none>"))
    rp = REPO/("command-center/receipts/%s.json" % uid)
    if rp.is_file():
        try:
            rec = json.loads(rp.read_text(encoding="utf-8"))
            rv = rec.get("reviewer") or {}
            chk("receipt-state-SUCCESS", rec.get("state")=="SUCCESS", "state=%s" % rec.get("state"))
            chk("receipt-verdict-PASS", rv.get("verdict")=="PASS", "verdict=%s" % rv.get("verdict"))
            chk("receipt-independent", rv.get("independent") is True, "independent=%s" % rv.get("independent"))
        except Exception as exc:
            chk("receipt-parses", False, repr(exc)[:150])
    else:
        chk("receipt-exists", False, str(rp))
    results[uid]=r

print("="*100)
npass=0
for uid in UNITS:
    r=results[uid]
    bad=[c for c in r["checks"] if not c[1]]
    status = "PASS" if not bad else "FAIL"
    npass += (not bad)
    print("%-10s %s  checks=%d bad=%d" % (uid, status, len(r["checks"]), len(bad)))
    for n,okv,d in bad:
        print("           !! %s -> %s" % (n, d))
    if r.get("other_rows_flag"):
        print("           (info) other manifest rows: %s" % (r["other_rows_flag"],))
    if r.get("bytes_field") is not None and r["bytes_field"] != r["live_bytes"]:
        print("           (info) manifest bytes=%s vs live=%s (pre-normalization size)" % (r["bytes_field"], r["live_bytes"]))
print("="*100)
print("TOTAL %d/%d units fully green" % (npass, len(UNITS)))
