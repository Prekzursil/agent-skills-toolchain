#!/usr/bin/env python3
"""Independent reviewer battery, wave 3 shard 9 round 3 (review:w3s9 r3).

Contract per spawn: for EACH of the 12 units adversarially verify
  (1) artifact exists/non-empty/parses/not-self-blocked at catalog output_path
  (2) live probes re-run exit 0 (every executable command recorded in the receipt)
  (3) sha256 (CRLF->LF) matches UNIT-ARTIFACT-MANIFEST.json row
  (4) output_schema validates
ALL hold -> close receipt (reviewer PASS, independent, SUCCESS). ANY fails -> FAIL, receipt untouched.

Binding rule (uniform across all 12, stated up front, not gerrymandered per unit):
  probes_rerun_exit0 binds on EVERY dict anywhere in the receipt JSON carrying a
  non-empty string "command" field; a command passes iff it re-runs exit 0 with
  non-empty stdout. Exit-0 with empty stdout = NOOP = fail. Same rule as r1/r2.
Runtime pinned: Git Bash C:\\Program Files\\Git\\bin\\bash.exe, python3 -> /c/Python314/python3
(RT-PROOF captured per command). Schema: estate-canonical platform/lib/schema_resolver
validate_artifact (instrument 1) + raw draft-2020-12 whole-doc against the shim's
$ref physical target on disk (instrument 2).
"""
import hashlib, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(r"C:\Users\Prekzursil\p2-g1")
OUT = ROOT / "_reviewer-w3s9-r3"
BASH = r"C:\Program Files\Git\bin\bash.exe"
ROOT_POSIX = "/c/Users/Prekzursil/p2-g1"
IDS = ["IMP-0022","IMP-0031","IMP-0035","IMP-0036","IMP-0037","IMP-0038",
       "IMP-0041","IMP-0044","IMP-0051","IMP-0068","IMP-0070","IMP-0084"]
TIMEOUT = 180

def sha_norm(p: Path):
    b = p.read_bytes()
    raw = hashlib.sha256(b).hexdigest()
    norm = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()
    return raw, norm, len(b)

def walk_commands(node, path="$"):
    """Yield (json_pointer, command) for every dict with a non-empty str 'command'."""
    if isinstance(node, dict):
        c = node.get("command")
        if isinstance(c, str) and c.strip():
            yield path, c.strip()
        for k, v in node.items():
            if k == "command":
                continue
            yield from walk_commands(v, path + "/" + k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_commands(v, path + "[" + str(i) + "]")

def run_cmd(cmd):
    script = ('cd "' + ROOT_POSIX + '" || exit 125; '
              'echo "RT-PROOF python3=$(command -v python3) v=$(python3 --version 2>&1)" >&2; '
              '{ ' + cmd + ' ; }')
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    t0 = time.time()
    to = False
    try:
        cp = subprocess.run([BASH, "-c", script], capture_output=True, timeout=TIMEOUT,
                            env=env, cwd=str(ROOT))
        out, err, code = cp.stdout, cp.stderr, cp.returncode
    except subprocess.TimeoutExpired as e:
        out = e.stdout or b""
        err = e.stderr or b""
        code = -1
        to = True
    dt = time.time() - t0
    o = out.decode("utf-8", "replace")
    e2 = err.decode("utf-8", "replace")
    rt = ""
    for line in e2.splitlines():
        if line.startswith("RT-PROOF"):
            rt = line
            break
    ok = (code == 0) and (len(o.strip()) > 0) and (not to)
    return {"command": cmd, "exit": code, "timeout": to, "seconds": round(dt, 1),
            "stdout_len": len(o.strip()), "stderr_len": len(e2.strip()),
            "stdout_head": o.strip()[:300], "stderr_head": e2.strip()[:300],
            "rt_proof": rt,
            "verdict": "PASS" if ok else "FAIL"}

def _file_uri_to_path(ref):
    # file:///C:/x/y -> C:/x/y ; file:///C:/x/y#/frag -> strip fragment
    t = ref.split("#", 1)[0][len("file://"):]
    while t.startswith("/"):
        t = t[1:]
    return Path(t)

def schema_errors(doc, declared):
    """Two mechanically independent instruments."""
    res = {"declared": declared, "instrument1_resolver": None, "instrument2_raw": None}
    parts = [s.strip() for s in str(declared).split("+") if s.strip()]
    sys.path.insert(0, str(ROOT / "platform" / "lib"))
    import schema_resolver as sr
    errs1 = []
    for part in parts:
        try:
            errs1 += sr.validate_artifact(doc, part)
        except Exception as ex:
            errs1.append("<resolver-error> " + part + ": " + type(ex).__name__ + ": " + str(ex))
    res["instrument1_resolver"] = errs1
    import jsonschema
    errs2 = []
    for part in parts:
        try:
            shim = json.loads((ROOT / part).read_bytes().decode("utf-8"))
            ref = shim.get("$ref") if isinstance(shim, dict) else None
            if ref and ref.startswith("file:"):
                phys = json.loads(_file_uri_to_path(ref).read_bytes().decode("utf-8"))
            elif ref:
                phys = json.loads(((ROOT / part).parent / ref).read_bytes().decode("utf-8"))
            else:
                phys = shim
            v = jsonschema.Draft202012Validator(phys)
            for err in v.iter_errors(doc):
                loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
                errs2.append(part + "::" + loc + ": " + err.message)
        except Exception as ex:
            errs2.append("<raw-error> " + part + ": " + type(ex).__name__ + ": " + str(ex))
    res["instrument2_raw"] = errs2
    res["valid"] = (not errs1) and (not errs2)
    return res

def manifest_for(uid):
    p = ROOT / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if not p.is_file():
        return None, None
    return p, json.loads(p.read_bytes().decode("utf-8"))

def deep_unit(uid, byid):
    cat = byid[uid]
    out = {"unit": uid, "output_path": cat.get("output_path"),
           "declared_schema": cat.get("output_schema"), "checks": {}}
    rp = ROOT / cat["output_path"]
    c = out["checks"]
    if not rp.is_file():
        c["artifact_ok"] = False
        out["artifact_fail"] = "missing"
        return out
    raw_s, norm_s, nbytes = sha_norm(rp)
    try:
        doc = json.loads(rp.read_bytes().decode("utf-8"))
        parses, perr = True, None
    except Exception as ex:
        doc, parses, perr = None, False, type(ex).__name__ + ": " + str(ex)
    state = doc.get("state") if isinstance(doc, dict) else None
    status = doc.get("status") if isinstance(doc, dict) else None
    c["artifact_ok"] = bool(parses and nbytes > 0 and state not in ("BLOCKED", "FAILED")
                            and status not in ("BLOCKED", "FAILED"))
    out["artifact_state"] = state
    out["artifact_status"] = status
    out["live_sha_raw"], out["live_sha_lf"], out["live_bytes"] = raw_s, norm_s, nbytes
    if not parses:
        c["artifact_ok"] = False
        out["artifact_fail"] = perr
    mp, man = manifest_for(uid)
    row = None
    if man:
        rows = man.get("artifacts") or []
        row = None
        for r in rows:
            if r.get("path") == cat["output_path"]:
                row = r
                break
        out["manifest_row_sha"] = row.get("sha256") if row else None
        c["manifest_sha_row"] = bool(row and row.get("sha256") == norm_s)
        drift = []
        for r in rows:
            f = ROOT / r["path"]
            if not f.is_file():
                drift.append({"path": r["path"], "problem": "missing"})
            else:
                rr, rn, nb = sha_norm(f)
                if rn != r.get("sha256"):
                    drift.append({"path": r["path"], "problem": "sha-drift",
                                  "manifest": r.get("sha256"), "live_lf": rn})
        out["manifest_other_rows_drift"] = drift
    else:
        c["manifest_sha_row"] = False
        out["manifest_missing"] = str(mp)
    c["output_schema_validates"] = False
    if parses:
        out["schema"] = schema_errors(doc, cat["output_schema"])
        c["output_schema_validates"] = out["schema"]["valid"]
    cmds = list(dict.fromkeys(walk_commands(doc))) if parses else []
    reports = []
    for ptr, cmd in cmds:
        r = run_cmd(cmd)
        r["where"] = ptr
        reports.append(r)
        print("  [" + uid + "] " + r["verdict"] + " exit=" + str(r["exit"]) + " " + ptr + " " + cmd[:90], flush=True)
    out["probe_report"] = reports
    c["probes_rerun_exit0"] = bool(reports) and all(r["verdict"] == "PASS" for r in reports)
    out["ALL_HOLD"] = all(bool(v) for v in c.values())
    return out

def main():
    cat = json.loads((ROOT / "command-center" / "WORK-UNIT-CATALOG.json").read_bytes().decode("utf-8"))
    byid = {}
    for u in cat["work_units"]:
        byid[u.get("id")] = u
    missing = [i for i in IDS if i not in byid]
    assert not missing, "units absent from catalog: " + repr(missing)
    print("== Phase A: static sweep of all receipts (positive control + tally) ==", flush=True)
    sys.path.insert(0, str(ROOT / "platform" / "lib"))
    import schema_resolver as sr
    tally = {"total_units": len(byid), "receipts_present": 0, "parse_ok": 0,
             "state_SUCCESS": 0, "self_blocked": 0, "manifest_row_match": 0,
             "schema_valid": 0, "green_static": 0, "green_static_ids": []}
    for uid, entry in sorted(byid.items()):
        rp = ROOT / entry["output_path"]
        if not rp.is_file():
            continue
        tally["receipts_present"] += 1
        try:
            doc = json.loads(rp.read_bytes().decode("utf-8"))
        except Exception:
            continue
        tally["parse_ok"] += 1
        st = doc.get("state")
        if st == "SUCCESS":
            tally["state_SUCCESS"] += 1
        if st in ("BLOCKED", "FAILED") or doc.get("status") in ("BLOCKED", "FAILED"):
            tally["self_blocked"] += 1
        _, norm_s, _ = sha_norm(rp)
        _, man = manifest_for(uid)
        rowok = False
        if man:
            row = None
            for r in (man.get("artifacts") or []):
                if r.get("path") == entry["output_path"]:
                    row = r
                    break
            rowok = bool(row and row.get("sha256") == norm_s)
        if rowok:
            tally["manifest_row_match"] += 1
        parts = [s.strip() for s in str(entry["output_schema"]).split("+") if s.strip()]
        ok = True
        for part in parts:
            try:
                if sr.validate_artifact(doc, part):
                    ok = False
                    break
            except Exception:
                ok = False
                break
        if ok:
            tally["schema_valid"] += 1
        if st == "SUCCESS" and rowok and ok:
            tally["green_static"] += 1
            tally["green_static_ids"].append(uid)
    (OUT / "phaseA_tally.json").write_bytes(json.dumps(tally, indent=1).encode("utf-8"))
    brief = dict((k, v) for k, v in tally.items() if k != "green_static_ids")
    print(json.dumps(brief, indent=1), flush=True)
    print("== Phase B: deep verification of the 12 shard units ==", flush=True)
    results = {}
    for uid in IDS:
        print("-- " + uid, flush=True)
        results[uid] = deep_unit(uid, byid)
        results[uid]["verdict"] = "PASS" if results[uid]["ALL_HOLD"] else "FAIL"
        print("   => " + results[uid]["verdict"] + " checks=" + json.dumps(results[uid]["checks"]), flush=True)
    (OUT / "r3_results.json").write_bytes(json.dumps(results, indent=1).encode("utf-8"))
    verd = dict((u, results[u]["verdict"]) for u in IDS)
    (OUT / "VERDICTS-w3s9-r3.json").write_bytes(json.dumps({
        "wave": "3", "shard": "9", "round": "r3",
        "reviewer": "claude-opus-5-5 independent reviewer review:w3s9 r3 2026-10-26 (_reviewer-w3s9-r3/verify.py)",
        "units": len(IDS), "verdict": verd,
        "binding_rule": "probes_rerun_exit0 on EVERY dict in the receipt carrying a string 'command'; PASS iff exit 0 + non-empty stdout; uniform across all 12 (same rule as r1/r2). Schema: resolver + raw draft-2020-12, both must be clean.",
        "results_file": "_reviewer-w3s9-r3/r3_results.json",
    }, indent=1).encode("utf-8"))
    print("VERDICTS: " + json.dumps(verd), flush=True)

if __name__ == "__main__":
    main()
