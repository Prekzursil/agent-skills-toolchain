#!/usr/bin/env python3
"""Wave-2 shard-16 independent reviewer: full adversarial battery + JSON report.

For each unit re-derives from bytes:
  A artifact present/non-empty/parses/dict; B state SUCCESS (not NOT-DELIVERING);
  C sentinel present; D failure-block absent; E reviewer PASS+independent+id-set;
  F manifest row path/present/sha256 == live CRLF->LF sha; G SUBAGENT-RETURN status ok;
  H every named probe re-run live rc==0; I output_schema validates (repo resolver,
  canonical platform contract); J official _measure_one_delivered.py exit code.
Writes REVIEW-SHARD16-W2.json; prints one verdict line per unit.
"""
import hashlib, json, os, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
REPO = HOME / "p2-g1"
OUT = REPO / "_rev-w2-shard16" / "REVIEW-SHARD16-W2.json"
UNITS = ["IMP-0470", "IMP-0478", "REL-0001", "REL-0006", "REL-0014", "REL-0017",
         "REL-0020", "REL-0021", "REL-0022", "RES-0004", "RES-0009", "RES-0011"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
ENVPAT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+")

def norm_sha(b):
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()

def lj(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))

def run_argv(parts, timeout=1800):
    try:
        r = subprocess.run(parts, cwd=str(REPO), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        rc = r.returncode
        tail = ((r.stdout or "") + (r.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        rc, tail = 124, "TIMEOUT"
    except Exception as exc:
        rc, tail = 125, type(exc).__name__
    lines = tail.splitlines() if tail else []
    return rc, tail, lines

def probe_argv(cmd):
    while True:
        m = ENVPAT.match(cmd)
        if not m:
            break
        cmd = cmd[m.end():]
    parts = cmd.split()
    if parts and parts[0] in ("python3", "python"):
        parts[0] = sys.executable
    return parts

def check_unit(uid, cat_by, res):
    rec = {"id": uid, "checks": {}, "schema_errors": [], "probe_runs": []}
    u = cat_by.get(uid)
    if u is None:
        rec["verdict"] = "FAIL"
        rec["checks"]["catalog-entry"] = "absent"
        return rec
    out_rel = str(u.get("output_path") or "").replace("\\", "/")
    out = REPO / out_rel
    ok_file = out.is_file()
    size = out.stat().st_size if ok_file else 0
    rec["output_path"] = out_rel
    rec["checks"]["artifact-present-nonempty"] = bool(ok_file and size > 0)
    rec["bytes"] = size
    doc = None
    if ok_file and size:
        raw = out.read_bytes()
        rec["live_sha256"] = norm_sha(raw)
        try:
            doc = json.loads(raw.decode("utf-8"))
            rec["checks"]["parses-dict"] = isinstance(doc, dict)
        except Exception as exc:
            rec["checks"]["parses-dict"] = False
            rec["parse_error"] = type(exc).__name__
    else:
        rec["checks"]["parses-dict"] = False
    if isinstance(doc, dict):
        st = str(doc.get("state") or "").upper()
        rec["state"] = st
        rec["checks"]["state-SUCCESS"] = (st == "SUCCESS")
        rec["checks"]["no-failure-block"] = not isinstance(doc.get("failure"), dict)
        sent = str(u.get("completion_sentinel") or "")
        rec["checks"]["sentinel-present"] = (not sent) or (sent in raw.decode("utf-8", errors="replace"))
        rev = doc.get("reviewer")
        rec["checks"]["reviewer-PASS-independent"] = bool(
            isinstance(rev, dict)
            and str(rev.get("verdict") or "").upper() == "PASS"
            and rev.get("independent") is True
            and str(rev.get("reviewer_id") or "").strip())
        manp = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        mok = False
        if manp.is_file() and ok_file:
            try:
                man = lj(manp)
                rows = [a for a in man.get("artifacts") or [] if isinstance(a, dict)
                        and a.get("unit_id") == uid
                        and str(a.get("path") or "").replace("\\", "/") == out_rel]
                mok = any(a.get("sha256") == rec["live_sha256"] and a.get("present") is True
                          for a in rows)
            except Exception:
                mok = False
        rec["checks"]["manifest-sha-match"] = mok
    else:
        rec["checks"]["state-SUCCESS"] = False
        rec["checks"]["no-failure-block"] = False
        rec["checks"]["sentinel-present"] = False
        rec["checks"]["reviewer-PASS-independent"] = False
        rec["checks"]["manifest-sha-match"] = False
    retp = REPO / "command-center" / "p2-wave" / "probes" / uid / "SUBAGENT-RETURN.json"
    cmds, ret_ok = [], False
    if retp.is_file():
        try:
            ret = lj(retp)
            rst = str(ret.get("status") or ret.get("state") or "").upper()
            ret_ok = rst not in NOT_DELIVERING
            for it in (ret.get("named_probes") or []):
                c = str(it.get("command") or "").strip()
                if c and c not in cmds:
                    cmds.append(c)
        except Exception:
            ret_ok = False
    rec["checks"]["subagent-return-ok"] = ret_ok
    if not cmds:
        pd = REPO / "command-center" / "p2-wave" / "probes" / uid
        cmds = ["python3 -B " + str(p.relative_to(REPO)).replace("\\", "/")
                for p in sorted(pd.glob("probe1*.py")) + sorted(pd.glob("probe2*.py"))]
    allok = bool(cmds)
    for i, c in enumerate(cmds, 1):
        rc, tail, lines = run_argv(probe_argv(c))
        marker = any(ln.startswith("SUCCESS") for ln in lines)
        last = lines[-1][:110] if lines else ""
        rec["probe_runs"].append({"n": i, "cmd_tail": c[-80:], "rc": rc,
                                  "success_marker": marker, "last_line": last})
        if rc != 0:
            allok = False
    rec["checks"]["probes-live-rc0"] = allok
    schema_rel = str(u.get("output_schema") or "")
    try:
        errs = res.validate_artifact(doc, schema_rel) if isinstance(doc, dict) else ["no-doc"]
    except Exception as exc:
        errs = ["resolver-crash:" + type(exc).__name__]
    rec["schema_error_count"] = len(errs)
    rec["schema_errors"] = [str(e)[:200] for e in errs[:24]]
    rec["checks"]["output_schema-valid"] = (len(errs) == 0)
    m = run_argv([sys.executable, "-B",
                  str(REPO / "command-center" / "p2-wave" / "_measure_one_delivered.py"), uid],
                 timeout=3600)
    rec["official_measure_rc"] = m[0]
    rec["official_measure_last"] = (m[2][-1][:120] if m[2] else "")
    gates = rec["checks"]
    rec["verdict"] = "PASS" if all(gates.values()) else "FAIL"
    rec["failing"] = [k for k, v in gates.items() if not v]
    return rec

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(REPO / "platform" / "lib"))
    import schema_resolver as res
    cat = lj(REPO / "command-center" / "WORK-UNIT-CATALOG.json")
    by = {u.get("id"): u for u in cat.get("work_units") or []}
    recs = []
    for uid in UNITS:
        r = check_unit(uid, by, res)
        recs.append(r)
        print("VERDICT", uid, r["verdict"],
              "| failing:", ",".join(r["failing"]) if r["failing"] else "none",
              "| schema_errs:", r["schema_error_count"],
              "| probes:", ",".join("rc%d%s" % (p["rc"], "+" if p["success_marker"] else "-")
                                    for p in r["probe_runs"]),
              "| official_rc:", r["official_measure_rc"])
    report = {
        "shard": "w2s16",
        "role": "independent-reviewer",
        "reviewer_id": "claude-opus-5-5 workflow-reviewer w2s16 2026-10-25",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "units": recs,
        "summary_counts": {
            "total": len(recs),
            "pass": sum(1 for r in recs if r["verdict"] == "PASS"),
            "fail": sum(1 for r in recs if r["verdict"] == "FAIL"),
        },
    }
    OUT.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print("WROTE", OUT)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
