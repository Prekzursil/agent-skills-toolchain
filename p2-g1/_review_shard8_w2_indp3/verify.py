import hashlib, importlib.util, json, os, subprocess, sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")

def sha_lf(raw):
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()

def load_resolver():
    spec = importlib.util.spec_from_file_location(
        "sr_indp3", REPO / "platform" / "lib" / "schema_resolver.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sr_indp3"] = mod
    spec.loader.exec_module(mod)
    return mod

def raw_schema_errors(doc, schema_rel):
    import jsonschema
    sp = REPO / schema_rel
    schema = json.loads(sp.read_text(encoding="utf-8"))
    dia = schema.get("$schema", "")
    if "2020-12" in dia:
        V = jsonschema.Draft202012Validator
    else:
        V = jsonschema.Draft7Validator
    errs = []
    resolver = jsonschema.RefResolver(base_uri=sp.as_uri(), referrer=schema)
    for e in V(schema, resolver=resolver).iter_errors(doc):
        loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
        errs.append(loc + ": " + e.message[:250])
    return errs

def run_probe(uid, fname):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run([sys.executable, "-B", "command-center/p2-wave/probes/" + uid + "/" + fname],
                       cwd=str(REPO), capture_output=True, text=True, timeout=300, env=env)
    out = ((p.stdout or "") + "\n" + (p.stderr or "")).strip()
    all_ok = "not-emitted"
    last_json = None
    for line in reversed(out.splitlines()):
        s = line.strip()
        if s.startswith("{"):
            try:
                j = json.loads(s)
            except Exception:
                continue
            if "all_ok" in j:
                all_ok = j.get("all_ok")
                last_json = j
                break
    return p.returncode, all_ok, (last_json or {}), out[-500:]

IDS  = ["CNF-0077","CNF-0089","CNF-0129","CNF-0142","CNF-0147","CNF-0149",
        "CNF-0152","CNF-0153","CNF-0158","CNF-0163","CNF-0166","CNF-0167"]
OUT  = REPO / "_review_shard8_w2_indp3/out.json"

def main():
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    by_id = {u.get("id"): u for u in cat["work_units"]}
    resolver = load_resolver()
    res = {}
    for uid in IDS:
        R = {"unit": uid}
        fatal = []
        ent = by_id.get(uid)
        if not ent:
            R["fatal"] = ["no-catalog-entry"]
            R["VERDICT"] = "FAIL"
            res[uid] = R
            continue
        out_rel = ent.get("output_path")
        sch_rel = ent.get("output_schema")
        R["output_path"] = out_rel
        R["output_schema"] = sch_rel
        if not out_rel:
            fatal.append("catalog-output_path-blank")
        doc = None
        art = (REPO / out_rel) if out_rel else None
        if art is None or not art.is_file():
            R["artifact-exists"] = False
            fatal.append("artifact-missing")
        else:
            R["artifact-exists"] = True
            raw = art.read_bytes()
            R["artifact-bytes"] = len(raw)
            if len(raw) == 0:
                fatal.append("artifact-empty")
            try:
                doc = json.loads(raw.decode("utf-8"))
                R["parses"] = True
            except Exception as e:
                R["parses"] = False
                fatal.append("artifact-unparseable:" + type(e).__name__)
            text = raw.decode("utf-8", errors="replace")
            st = doc.get("state") if isinstance(doc, dict) else None
            R["self-state-field"] = st
            if isinstance(st, str) and st.upper() in ("BLOCKED", "FAILED"):
                fatal.append("artifact-self-declared-" + st.upper())
            marker = "SUCCESS:" + uid
            R["sentinel-present"] = marker in text
            if marker not in text:
                fatal.append("sentinel-SUCCESS-marker-absent")
            R["live-sha256-lf"] = sha_lf(raw)
        rp = REPO / "command-center" / "receipts" / (uid + ".json")
        if not rp.is_file():
            R["receipt"] = None
            fatal.append("receipt-missing")
        else:
            rec = json.loads(rp.read_text(encoding="utf-8"))
            rv = rec.get("reviewer") or {}
            R["receipt"] = {"state": rec.get("state"), "verdict": rv.get("verdict"),
                            "independent": rv.get("independent"), "reviewer_id": rv.get("reviewer_id")}
            if rec.get("state") == "SUCCESS" and (rv.get("verdict") != "PASS" or rv.get("independent") is not True):
                fatal.append("receipt-core-violation:SUCCESS-without-independent-PASS")
            thr = rec.get("min_bytes_threshold")
            if isinstance(thr, int) and art is not None and art.is_file() and art.stat().st_size < thr:
                fatal.append("below-min-bytes:%d<%d" % (art.stat().st_size, thr))
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        probes = sorted(x.name for x in pdir.glob("probe*.py")) if pdir.is_dir() else []
        R["probes"] = {}
        for fn in probes:
            try:
                rc, aok, j, tail = run_probe(uid, fn)
            except subprocess.TimeoutExpired:
                rc, aok, j, tail = -9, "timeout", {}, "TIMEOUT>300s"
            R["probes"][fn] = {"rc": rc, "all_ok": aok}
            if rc != 0:
                fatal.append("probe-%s-exit%s tail=%s" % (fn, rc, tail.replace("\n", " | ")[:200]))
            elif aok not in (True, "not-emitted"):
                fatal.append("probe-%s-all_ok=%r" % (fn, aok))
        if not probes:
            fatal.append("no-probe-scripts-found")
        man_p = pdir / "UNIT-ARTIFACT-MANIFEST.json"
        if not man_p.is_file():
            fatal.append("manifest-missing")
        else:
            man = json.loads(man_p.read_text(encoding="utf-8"))
            rows = man.get("artifacts") or []
            prim = [r for r in rows if r.get("role") == "primary" and r.get("path") == out_rel]
            R["manifest-primary-present"] = bool(prim)
            if not prim:
                fatal.append("manifest-no-primary-row")
            else:
                if prim[0].get("sha256") != R.get("live-sha256-lf"):
                    fatal.append("manifest-primary-sha-mismatch manifest=%s live=%s" % (
                        str(prim[0].get("sha256"))[:16], str(R.get("live-sha256-lf"))[:16]))
                if isinstance(prim[0].get("bytes"), int) and art is not None and art.is_file() and prim[0]["bytes"] != art.stat().st_size:
                    fatal.append("manifest-primary-bytes-mismatch")
            mism = []
            for r in rows:
                f = REPO / str(r.get("path", "_"))
                if not f.is_file():
                    mism.append(str(r.get("path")) + ":absent")
                elif sha_lf(f.read_bytes()) != r.get("sha256"):
                    mism.append(str(r.get("path")) + ":sha-mismatch")
            R["manifest-row-mismatches"] = mism
            if mism:
                fatal.append("manifest-rehash-mismatch:" + ";".join(mism[:5]))
        if doc is None:
            fatal.append("schema-not-run:artifact-unparsed")
        else:
            try:
                rerrs = resolver.validate_artifact(doc, sch_rel)
            except Exception as e:
                rerrs = ["resolver-crash:%s:%s" % (type(e).__name__, str(e)[:150])]
            try:
                werrs = raw_schema_errors(doc, sch_rel)
            except Exception as e:
                werrs = ["raw-crash:%s:%s" % (type(e).__name__, str(e)[:150])]
            R["schema-resolver-errors"] = rerrs
            R["schema-raw-errors"] = werrs
            if rerrs:
                fatal.append("output-schema-invalid(resolver):%d first=%s" % (len(rerrs), str(rerrs[0])[:170]))
            if werrs:
                fatal.append("output-schema-invalid(raw):%d first=%s" % (len(werrs), str(werrs[0])[:170]))
        R["fatal"] = fatal
        R["VERDICT"] = "FAIL" if fatal else "ALL-CHECKS-HOLD"
        res[uid] = R
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    for uid in IDS:
        v = res[uid]["VERDICT"]
        fl = res[uid].get("fatal") or []
        print(uid, v, ("| " + "; ".join(fl)[:230]) if fl else "")
    print("written:", OUT)

if __name__ == "__main__":
    main()
