#!/usr/bin/env python3
"""Independent reviewer harness: wave-4 shard-12 candidate units (union of the two
adjacent chunk derivations). Fail-closed per unit:
  C1 catalog entry (output_path, output_schema, dependencies)
  C2 receipt parses, non-empty, state==SUCCESS, not success_withheld, sentinel matches
  C3 reviewer closure: verdict==PASS and independent==true and reviewer_id != produced_by
  C4 every receipt.artifact_paths exists + non-empty
  C5 UNIT-ARTIFACT-MANIFEST rows: sha256(CRLF-normalized live bytes) == row.sha256
  C6 live probes (receipt.tests[].command + SUBAGENT-RETURN named_probes) re-run exit 0
  C7 output_schema validated via platform/lib/schema_resolver (empty error list)
ALL hold -> CONFIRM (existing PASS closure stays SUCCESS; no write needed).
ANY fail -> FAIL verdict with the precise check; receipt untouched.
Results written incrementally to _verify_results.json (write-as-you-go).
"""
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
OUT = REPO / "_p2shard12-w4/_verify_results.json"
sys.path.insert(0, str(REPO / "platform" / "lib"))
os.environ["AST_INTEGRATE_ROOT"] = str(REPO)

CHUNK_A = ["IMP-0261", "IMP-0264", "IMP-0269", "IMP-0270", "IMP-0271", "IMP-0272",
           "IMP-0273", "IMP-0274", "IMP-0275", "IMP-0279", "IMP-0303", "IMP-0304"]
CHUNK_B = ["IMP-0321", "IMP-0360", "IMP-0372", "IMP-0374", "IMP-0390", "IMP-0402",
           "IMP-0409", "IMP-0415", "IMP-0421", "IMP-0423", "IMP-0441", "IMP-0442"]
UNITS = CHUNK_A + CHUNK_B


def lf_sha(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def run_probe(cmd, timeout=900):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
    while m:
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
    try:
        argv = shlex.split(cmd, posix=True)
    except ValueError:
        argv = None
    try:
        if argv:
            p = subprocess.run(argv, cwd=str(REPO), capture_output=True, text=True,
                               timeout=timeout, env=env)
        else:
            p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                               text=True, timeout=timeout, env=env)
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except FileNotFoundError as e:
        return 127, "NOT-FOUND " + str(e)


results = {}


def save():
    OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")


import schema_resolver as sr  # noqa: E402

for uid in UNITS:
    r = {"id": uid, "checks": {}, "probe_runs": []}
    try:
        # C1 catalog
        cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
        unit = next((u for u in cat["work_units"] if u.get("id") == uid), None)
        if not unit:
            r["checks"]["C1_catalog"] = "FAIL: no catalog entry"
            results[uid] = r
            save()
            continue
        missing = [k for k in ("output_path", "output_schema", "dependencies") if not unit.get(k)]
        r["checks"]["C1_catalog"] = "PASS" if not missing else "FAIL: missing " + repr(missing)
        r["catalog_output_schema"] = unit.get("output_schema")
        if missing:
            results[uid] = r
            save()
            continue

        # C2 receipt
        out_path = REPO / unit["output_path"]
        if not out_path.is_file() or out_path.stat().st_size == 0:
            r["checks"]["C2_receipt"] = "FAIL: output_path missing/empty: " + unit["output_path"]
            results[uid] = r
            save()
            continue
        try:
            doc = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception as e:
            r["checks"]["C2_receipt"] = "FAIL: parse " + type(e).__name__ + ": " + str(e)
            results[uid] = r
            save()
            continue
        st = doc.get("state")
        if st != "SUCCESS":
            r["checks"]["C2_receipt"] = "FAIL: state=" + str(st)
            results[uid] = r
            save()
            continue
        if doc.get("success_withheld") is True:
            r["checks"]["C2_receipt"] = "FAIL: success_withheld=true"
            results[uid] = r
            save()
            continue
        sent = doc.get("sentinel")
        exp_sent = "SUCCESS:" + uid
        if sent != exp_sent:
            r["checks"]["C2_receipt"] = "FAIL: sentinel mismatch: " + repr(sent)
            results[uid] = r
            save()
            continue
        r["checks"]["C2_receipt"] = "PASS"

        # C3 reviewer closure
        rv = doc.get("reviewer") or {}
        ok = isinstance(rv, dict) and rv.get("verdict") == "PASS" and rv.get("independent") is True
        self_cert = isinstance(rv, dict) and rv.get("reviewer_id") and \
            str(rv.get("reviewer_id")) == str(doc.get("produced_by"))
        if isinstance(rv, dict):
            r["reviewer"] = {k: rv.get(k) for k in
                             ("reviewer_id", "verdict", "independent", "vendor",
                              "fresh_context", "reviewed_at")}
        r["produced_by"] = doc.get("produced_by")
        if ok and not self_cert:
            r["checks"]["C3_reviewer"] = "PASS"
        else:
            r["checks"]["C3_reviewer"] = ("FAIL: verdict/independent="
                                          + str(rv.get("verdict") if isinstance(rv, dict) else None)
                                          + "/" + str(rv.get("independent") if isinstance(rv, dict) else None)
                                          + " self_cert=" + str(self_cert))

        # C4 artifact paths
        missing = []
        for ap in doc.get("artifact_paths") or []:
            p = Path(ap) if Path(ap).is_absolute() else REPO / ap
            if not p.is_file() or p.stat().st_size == 0:
                missing.append(ap)
        r["checks"]["C4_artifacts"] = "PASS" if not missing else "FAIL missing/empty: " + repr(missing)

        # C5 manifest sha
        man_p = REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        if not man_p.is_file():
            r["checks"]["C5_manifest"] = "FAIL: no UNIT-ARTIFACT-MANIFEST.json"
        else:
            man = None
            try:
                man = json.loads(man_p.read_text(encoding="utf-8"))
            except Exception as e:
                r["checks"]["C5_manifest"] = "FAIL: manifest parse " + type(e).__name__
            if man is not None:
                rows = {}
                for a in man.get("artifacts") or []:
                    if isinstance(a, dict) and a.get("path"):
                        rows[str(a["path"]).replace("\\", "/")] = a
                bad = []
                checked = 0
                for ap in doc.get("artifact_paths") or []:
                    rel = ap.replace("\\", "/")
                    row = rows.get(rel)
                    p = Path(ap) if Path(ap).is_absolute() else REPO / ap
                    if not p.is_file():
                        continue  # already C4-failed
                    checked += 1
                    if row is None:
                        bad.append(rel + ":NO-ROW")
                        continue
                    live = lf_sha(p)
                    if row.get("sha256") != live:
                        bad.append(rel + ":SHA manifest=" + str(row.get("sha256"))[:12]
                                   + " live=" + live[:12])
                r["manifest_rows_checked"] = checked
                r["checks"]["C5_manifest"] = "PASS" if not bad else "FAIL: " + repr(bad)

        # C6 live probes
        cmds = []
        for t in doc.get("tests") or []:
            c = t.get("command")
            if c and c not in cmds:
                cmds.append(c)
        ret_p = REPO / "command-center/p2-wave/probes" / uid / "SUBAGENT-RETURN.json"
        if ret_p.is_file():
            try:
                ret = json.loads(ret_p.read_text(encoding="utf-8"))
                for np in ret.get("named_probes") or []:
                    c = np.get("command")
                    if c and c not in cmds:
                        cmds.append(c)
            except Exception:
                pass
        probe_fail = []
        for c in cmds:
            rc, out = run_probe(c)
            tail = out[-160:].replace("\n", " | ")
            r["probe_runs"].append({"cmd": c, "rc": rc, "tail": tail})
            if rc != 0:
                probe_fail.append("rc=" + str(rc) + " " + c + " :: " + tail)
        if cmds and not probe_fail:
            r["checks"]["C6_probes"] = "PASS"
        elif not cmds:
            r["checks"]["C6_probes"] = "FAIL: no probe commands registered"
        else:
            r["checks"]["C6_probes"] = "FAIL: " + repr(probe_fail)

        # C7 schema
        try:
            errs = sr.validate_artifact(doc, unit["output_schema"])
            r["checks"]["C7_schema"] = "PASS" if not errs else "FAIL: " + repr(errs[:4])
        except Exception as e:
            r["checks"]["C7_schema"] = "FAIL: resolver " + type(e).__name__ + ": " + str(e)[:160]
    except Exception as e:
        r["checks"]["HARNESS"] = "FAIL: " + type(e).__name__ + ": " + str(e)[:200]
    verdict = "CONFIRM" if all(str(v) == "PASS" for v in r["checks"].values()) else "FAIL"
    r["verdict"] = verdict
    results[uid] = r
    save()
    line = uid + ": " + verdict + " " + " ".join(k + "=" + str(v)[:40] for k, v in r["checks"].items())
    print(line)

save()
conf = [u for u, rr in results.items() if rr.get("verdict") == "CONFIRM"]
fail = [u for u, rr in results.items() if rr.get("verdict") == "FAIL"]
print("")
print("CONFIRM " + str(len(conf)) + "  FAIL " + str(len(fail)))
for u in fail:
    print("FAIL", u, json.dumps(results[u]["checks"])[:400])
