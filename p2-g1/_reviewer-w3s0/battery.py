#!/usr/bin/env python3
# Wave-3 shard-0 INDEPENDENT REVIEWER battery (fail-closed).
import hashlib, json, os, subprocess, sys, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
PROBES = REPO / "command-center/p2-wave/probes"
MY12 = ["ADV-0005","ADV-0010","ADV-0014","ADV-0015","ADV-0018","ADV-0019",
        "ADV-0022","ADV-0023","ADV-0024","ADV-0028","ADV-0029","ADV-0037"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

def lf_sha(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

def run_probe(script):
    env = {}
    for k in ("PATH", "SYSTEMROOT", "COMSPEC", "TEMP", "TMP"):
        if k in os.environ:
            env[k] = os.environ[k]
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    r = subprocess.run([sys.executable, "-I", "-B", str(script)],
                       capture_output=True, text=True, timeout=600,
                       cwd=str(REPO), env=env)
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode, out.strip()[:400]

def validate_schema(doc, schema_path):
    from jsonschema.validators import validator_for
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    cls = validator_for(schema)
    cls.check_schema(schema)
    v = cls(schema)
    errs = []
    for err in sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errs.append(loc + ": " + err.message)
    return errs[:8]

results = {}
cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u.get("id"): u for u in cat["work_units"]}

for uid in MY12:
    res = {"unit_id": uid, "checks": {}, "fail_reasons": []}
    fails = res["fail_reasons"]
    u = byid.get(uid)
    if not u:
        fails.append("catalog-entry-absent")
        results[uid] = res
        continue
    out_rel = str(u.get("output_path") or "").replace("\\", "/")
    res["output_path"] = out_rel
    schema_rel = str(u.get("output_schema") or "")
    schema_rel = schema_rel.split(" profile=")[0].split(" + ")[0].split(" (")[0].split("#")[0].strip()
    res["output_schema"] = schema_rel
    art = REPO / out_rel
    if not art.is_file():
        fails.append("artifact-missing")
        results[uid] = res
        continue
    size = art.stat().st_size
    res["checks"]["artifact_bytes"] = size
    if size == 0:
        fails.append("artifact-empty")
        results[uid] = res
        continue
    if size < 1024:
        fails.append("artifact-under-1k:" + str(size))
    try:
        doc = json.loads(art.read_text(encoding="utf-8"))
        res["checks"]["parses"] = True
    except Exception as e:
        fails.append("artifact-unparseable:" + type(e).__name__)
        results[uid] = res
        continue
    st = str(doc.get("state") or "").upper()
    res["checks"]["artifact_state"] = st
    if st in NOT_DELIVERING:
        fails.append("artifact-self-declared:" + st)
    if str(doc.get("unit_id") or doc.get("id") or "") != uid:
        fails.append("artifact-unit-id-mismatch")
    pdir = PROBES / uid
    scripts = sorted(pdir.glob("probe1_*.py")) + sorted(pdir.glob("probe2_*.py"))
    res["checks"]["probes_run"] = {}
    for s in scripts:
        rc, out = run_probe(s)
        res["checks"]["probes_run"][s.name] = {"exit": rc, "out": out}
        if rc != 0:
            fails.append("probe-fail:" + s.name + ":rc=" + str(rc) + ":" + out[:120])
    man_p = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    if not man_p.is_file():
        fails.append("manifest-absent")
    else:
        try:
            man = json.loads(man_p.read_text(encoding="utf-8"))
        except Exception as e:
            fails.append("manifest-unparseable:" + type(e).__name__)
            man = None
        if man is not None:
            live = lf_sha(art)
            rows = [a for a in (man.get("artifacts") or []) if isinstance(a, dict)]
            match = [a for a in rows
                     if str(a.get("path") or "").replace("\\", "/") == out_rel
                     and str(a.get("sha256") or "") == live
                     and a.get("present") is True]
            res["checks"]["manifest_sha_match"] = bool(match)
            if not match:
                fails.append("manifest-sha-mismatch:live=" + live[:16])
    if schema_rel:
        sp = REPO / schema_rel
        if not sp.is_file():
            fails.append("schema-file-missing:" + schema_rel)
        else:
            errs = validate_schema(doc, sp)
            res["checks"]["schema_errors"] = errs
            if errs:
                fails.append("schema-invalid:" + str(len(errs)) + "err:" + errs[0][:120])
    rp = REPO / ("command-center/receipts/" + uid + ".json")
    if not rp.is_file():
        fails.append("receipt-missing")
    else:
        try:
            r = json.loads(rp.read_text(encoding="utf-8"))
        except Exception as e:
            fails.append("receipt-unparseable:" + type(e).__name__)
            r = None
        if r is not None:
            rstate = r.get("state")
            res["checks"]["receipt_state"] = rstate
            if str(r.get("unit_id") or "") != uid:
                fails.append("receipt-unit-id-mismatch")
            fc = (r.get("failure") or {}).get("classification") or []
            res["checks"]["failure_classification"] = fc
            if rstate != "BLOCKED":
                fails.append("receipt-state:" + str(rstate))
            if "reviewer-absent" not in fc:
                fails.append("failure-classification:" + repr(fc))
            rv = r.get("reviewer")
            res["checks"]["receipt_reviewer"] = rv
            if rv not in (None, {}):
                fails.append("receipt-reviewer-not-null(self-certified?)")
            mr = (r.get("manifest_registration") or {})
            if mr.get("registered") is not True:
                fails.append("manifest-not-registered")
            if ("SUCCESS:" + uid) not in rp.read_text(encoding="utf-8"):
                fails.append("sentinel-absent-in-receipt")
            res["checks"]["produced_by_role"] = (r.get("produced_by") or {}).get("role")
    results[uid] = res

verdicts = {}
hdr = "unit      bytes   state    probes         sha   schema  receipt   verdict"
print(hdr)
for uid in MY12:
    r = results.get(uid) or {"fail_reasons": ["no-result"], "checks": {}}
    f = r["fail_reasons"]
    ok = not f
    probes = r["checks"].get("probes_run", {})
    pstats = "/".join(("P" if v["exit"] == 0 else "F") for v in probes.values()) or "-"
    cells = [uid, str(r["checks"].get("artifact_bytes", "-")),
             str(r["checks"].get("artifact_state"))[:8], pstats[:14],
             str(r["checks"].get("manifest_sha_match")),
             ("OK" if not r["checks"].get("schema_errors") else "BAD"),
             str(r["checks"].get("receipt_state"))[:9],
             ("PASS" if ok else "FAIL")]
    print("{:9} {:>7} {:8} {:14} {:5} {:7} {:9} {}".format(*cells))
    if f:
        for x in f:
            print("    -> " + x)
    verdicts[uid] = "PASS" if ok else "FAIL"

out = {"verdicts": verdicts, "results": results}
(REPO / "_reviewer-w3s0/review-results.json").write_text(
    json.dumps(out, indent=1), encoding="utf-8")
print("")
npass = sum(1 for v in verdicts.values() if v == "PASS")
print("PASS:", npass, "/", len(MY12))
