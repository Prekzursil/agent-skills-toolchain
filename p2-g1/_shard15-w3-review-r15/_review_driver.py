#!/usr/bin/env python3
# Independent reviewer driver - wave 3 shard 15 (12 units), resume run 2026-10-26.
# Checks per unit: artifact exists/non-empty/parses/not-self-blocked at catalog
# output_path; live probes re-run (exit 0); CRLF-normalized sha256 vs
# probes/<id>/UNIT-ARTIFACT-MANIFEST.json; output_schema validation;
# receipt_core rule (SUCCESS requires reviewer PASS + independent).
import hashlib, json, os, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUTDIR = Path(__file__).resolve().parent
UNITS = ["IMP-0478", "REL-0001", "REL-0006", "REL-0014", "REL-0017", "REL-0020",
         "REL-0021", "REL-0022", "RES-0004", "RES-0009", "RES-0011", "RES-0020"]
PROBE_TIMEOUT = 240

def norm_sha(p):
    b = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest()

def main():
    entries = json.load(open(REPO / "_p2-shard15-w3-entries.json", encoding="utf-8"))
    catalog = json.load(open(REPO / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
    cu = {u.get("id"): u for u in catalog["work_units"]}
    report = {}
    for uid in UNITS:
        r = {"unit": uid, "checks": {}, "fail": []}
        ce = cu.get(uid)
        if ce is None:
            r["fail"].append("catalog: unit id absent from WORK-UNIT-CATALOG.json")
            report[uid] = r
            continue
        out_rel = ce.get("output_path")
        sch_rel = ce.get("output_schema")
        art = REPO / out_rel
        raw = None
        # 1. artifact exists / non-empty / parses / not self-blocked
        if not art.exists():
            r["fail"].append("artifact-missing: " + out_rel)
        else:
            raw = art.read_bytes()
            if len(raw) == 0:
                r["fail"].append("artifact-empty")
            else:
                try:
                    doc = json.loads(raw.decode("utf-8"))
                    st = doc.get("state")
                    r["checks"]["state"] = st
                    if st in ("BLOCKED", "FAILED"):
                        r["fail"].append("artifact-self-blocked: state=" + str(st))
                    if st == "SUCCESS":
                        rv = doc.get("reviewer") or {}
                        ok_core = rv.get("verdict") == "PASS" and rv.get("independent") is True
                        r["checks"]["receipt_core"] = ok_core
                        if not ok_core:
                            r["fail"].append("receipt_core: state=SUCCESS without reviewer.verdict=PASS + independent=true")
                except Exception as ex:
                    r["fail"].append("artifact-unparsable: " + repr(ex))
        # 2. manifest row + sha match
        mpath = REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        if not mpath.exists():
            r["fail"].append("manifest-missing for " + uid)
        else:
            try:
                m = json.loads(mpath.read_bytes().decode("utf-8"))
                rows = [a for a in m.get("artifacts", []) if a.get("path") == out_rel]
                if not rows:
                    r["fail"].append("manifest: no artifact row for " + out_rel)
                elif raw is not None:
                    row = rows[0]
                    live = norm_sha(art)
                    r["checks"]["sha_match"] = (live == row.get("sha256"))
                    r["checks"]["sha_live"] = live
                    r["checks"]["sha_manifest"] = row.get("sha256")
                    if live != row.get("sha256"):
                        r["fail"].append("sha-mismatch: live CRLF-normalized sha256 != manifest row")
                    if row.get("bytes") != len(raw):
                        r["fail"].append("bytes-mismatch: live " + str(len(raw)) + " vs manifest " + str(row.get("bytes")))
            except Exception as ex:
                r["fail"].append("manifest-unparsable: " + repr(ex))
        # 3. schema validation
        spath = REPO / sch_rel
        if not spath.exists():
            r["fail"].append("schema-file-missing: " + sch_rel)
        elif raw:
            try:
                import jsonschema
                schema = json.loads(spath.read_bytes().decode("utf-8"))
                doc = json.loads(raw.decode("utf-8"))
                V = jsonschema.validators.validator_for(schema)
                V.check_schema(schema)
                errs = sorted(V(schema).iter_errors(doc), key=lambda e: list(e.path))
                r["checks"]["schema_errors"] = len(errs)
                if errs:
                    msgs = []
                    for e in errs[:5]:
                        msgs.append(str(list(e.path)) + ": " + e.message[:140])
                    r["fail"].append("schema-violation: " + "; ".join(msgs))
            except Exception as ex:
                r["fail"].append("schema-run-error: " + repr(ex))
        # 4. live probes
        pdir = REPO / "command-center/p2-wave/probes" / uid
        probes = sorted(pdir.glob("probe*.py")) if pdir.exists() else []
        if not probes:
            r["fail"].append("probes-missing: no probe*.py under probes/" + uid + "/")
        r["checks"]["probes"] = {}
        for pr in probes:
            t0 = time.time()
            try:
                cp = subprocess.run([sys.executable, "-B", str(pr)], cwd=str(pdir),
                                    capture_output=True, text=True, timeout=PROBE_TIMEOUT,
                                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
                rc = cp.returncode
                lines = (cp.stdout or "").strip().splitlines()
                tail = lines[-1] if lines else ""
                r["checks"]["probes"][pr.name] = {"rc": rc, "secs": round(time.time() - t0, 1), "tail": tail[:160]}
                if rc != 0:
                    errlines = (cp.stderr or "").strip().splitlines()
                    etail = errlines[-1] if errlines else ""
                    r["fail"].append("probe-failed: " + pr.name + " rc=" + str(rc) + " err=" + etail[:140])
            except subprocess.TimeoutExpired:
                r["fail"].append("probe-timeout: " + pr.name)
            except Exception as ex:
                r["fail"].append("probe-run-error: " + pr.name + ": " + repr(ex))
        r["verdict"] = "FAIL" if r["fail"] else "ALL-HOLD"
        report[uid] = r
        print(uid + ": " + r["verdict"] + ((" | " + "; ".join(r["fail"])) if r["fail"] else ""), flush=True)
    (OUTDIR / "review-report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    nfail = sum(1 for v in report.values() if v.get("verdict") == "FAIL")
    print("SUMMARY: " + str(len(report) - nfail) + "/" + str(len(report)) + " ALL-HOLD, " + str(nfail) + " FAIL", flush=True)

if __name__ == "__main__":
    main()
