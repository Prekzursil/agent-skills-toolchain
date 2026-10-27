"""W4 shard-12 INDEPENDENT REVIEWER driver (12 units).

Per unit, mechanically verified BY THIS REVIEWER (not the builder):
  A. receipt exists / non-empty / parses (catalog output_path)
  B. not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT
  C. admission gate: command-center/receipt_validate.py -> ACCEPT
  D. completion gate: platform/lib/receipt_schema_gate.py --json
       complete=true, zero schema errors, no UNSATISFIED condition
  E. declared output_schema (catalog) via platform/lib/schema_resolver.py -> 0 errors
  F. DELIVERED measure: command-center/p2-wave/_measure_one_delivered.py <UID>
       (re-runs live named probes itself; sha256 CRLF-normalized manifest match)
  G. reviewer literal: reviewer.verdict==PASS, independent==true
  H. receipt_core SUCCESS conditional: manifest_registration.registered==true
  I. independent sha256 recompute (CRLF->LF) vs probes/<id>/UNIT-ARTIFACT-MANIFEST.json
"""
from __future__ import annotations
import hashlib, importlib.util, json, os, subprocess, sys, time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
MINE = ["IMP-0461", "IMP-0465", "IMP-0476", "IMP-0478", "IMP-0480",
        "REL-0001", "REL-0006", "REL-0014", "REL-0017", "REL-0020",
        "REL-0021", "REL-0022"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
LOG = REPO / "_reviewer-w4s12" / "review_log.jsonl"
logf = LOG.open("a", encoding="utf-8")


def emit(obj):
    line = json.dumps(obj, ensure_ascii=False)
    logf.write(line + "\n")
    logf.flush()
    print(line, flush=True)


_rspec = importlib.util.spec_from_file_location("sr", REPO / "platform/lib/schema_resolver.py")
sr = importlib.util.module_from_spec(_rspec)
sys.modules["sr"] = _rspec
_rspec.loader.exec_module(sr)

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}


def run(cmd, timeout=2700, cwd=REPO):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                           timeout=timeout, env=env,
                           shell=isinstance(cmd, str))
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except Exception as e:
        return 125, type(e).__name__ + ": " + str(e)


def norm_sha(path: Path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


summary = {}
for uid in MINE:
    u = byid[uid]
    row = {"unit": uid, "checks": {}, "verdict": None, "fail_reasons": []}
    out_rel = str(u["output_path"]).replace("\\", "/")
    out = REPO / out_rel
    rec = None
    # A: exists / non-empty / parses
    if not out.is_file() or out.stat().st_size <= 0:
        row["checks"]["A_parse"] = "FAIL absent-or-empty"
        row["fail_reasons"].append("artifact-absent-or-empty")
    else:
        try:
            rec = json.loads(out.read_text(encoding="utf-8"))
            row["checks"]["A_parse"] = "ok"
        except Exception as e:
            row["checks"]["A_parse"] = "FAIL " + type(e).__name__
            row["fail_reasons"].append("unparseable:" + type(e).__name__)
    if isinstance(rec, dict):
        st = str(rec.get("state") or "").upper()
        row["state"] = st
        # B: not self-blocked
        row["checks"]["B_not_blocked"] = "ok" if st not in NOT_DELIVERING else "FAIL self-declared:" + st
        if st in NOT_DELIVERING:
            row["fail_reasons"].append("self-declared:" + st)
        # G: reviewer literals
        rev = rec.get("reviewer") or {}
        gv = (rev.get("verdict") == "PASS" and rev.get("independent") is True)
        row["checks"]["G_reviewer_pass_indep"] = "ok" if gv else (
            "FAIL verdict=%s indep=%s" % (rev.get("verdict"), rev.get("independent")))
        if not gv:
            row["fail_reasons"].append("reviewer-not-PASS-independent")
        # H: receipt_core SUCCESS conditional
        mr = rec.get("manifest_registration")
        reg = mr.get("registered") if isinstance(mr, dict) else None
        if reg is None and rec.get("registered") is not None:
            reg = rec.get("registered")
        row["checks"]["H_registered"] = "ok" if reg is True else "FAIL registered=%s" % reg
        if reg is not True:
            row["fail_reasons"].append("manifest_registration.registered-not-true")
        # E: declared output_schema
        ds = u.get("output_schema")
        try:
            errs = sr.validate_artifact(rec, ds)
            row["checks"]["E_declared_schema"] = "ok" if not errs else "FAIL %d errs" % len(errs)
            row["declared_schema_errors"] = [str(e)[:220] for e in (errs or [])][:6]
            if errs:
                row["fail_reasons"].append("declared-schema:%d-errors" % len(errs))
        except Exception as e:
            row["checks"]["E_declared_schema"] = ("FAIL resolver:" + type(e).__name__ + ":" + str(e))[:220]
            row["fail_reasons"].append("schema-resolver-error")
    else:
        row["checks"]["B_not_blocked"] = "FAIL unparseable"
        row["checks"]["G_reviewer_pass_indep"] = "FAIL unparseable"
        row["checks"]["H_registered"] = "FAIL unparseable"
        row["checks"]["E_declared_schema"] = "FAIL unparseable"
        row["fail_reasons"].append("receipt-unreadable")
    # C: admission gate
    rc, txt = run([sys.executable, "-I", "command-center/receipt_validate.py", out_rel])
    ok_c = (rc == 0 and "ACCEPT" in txt)
    row["checks"]["C_admission"] = "ok ACCEPT" if ok_c else "FAIL rc=%d %s" % (rc, txt.strip()[:200])
    if not ok_c:
        row["fail_reasons"].append("admission:rc%d" % rc)
    # D: completion gate
    rc, txt = run([sys.executable, "-I", "platform/lib/receipt_schema_gate.py", out_rel, "--json"])
    try:
        d = json.loads(txt)
        r0 = d[0] if isinstance(d, list) else d
        conds = r0.get("conditions") or {}
        unsat = sorted(k for k, v in conds.items() if v == "UNSATISFIED")
        nc = sorted(k for k, v in conds.items() if v == "NOT-CHECKED")
        serr = r0.get("schema_errors") or []
        ok_d = (rc == 0 and r0.get("complete") and not unsat and not serr)
        row["checks"]["D_completion"] = "ok complete" if ok_d else (
            "FAIL complete=%s unsat=%s nc=%s schema_errs=%d" % (r0.get("complete"), unsat, nc, len(serr)))
        row["gate_detail"] = {"complete": r0.get("complete"), "marker": r0.get("marker"),
                              "unsat": unsat, "not_checked": nc,
                              "schema_errors": [str(s)[:200] for s in serr[:6]]}
        if not ok_d:
            why = ("unsat=" + ",".join(map(str, unsat))) if unsat else (
                "schema-errs" if serr else "incomplete")
            row["fail_reasons"].append("completion-gate:" + why)
    except Exception as e:
        row["checks"]["D_completion"] = "FAIL gate-parse:%s rc=%d %s" % (type(e).__name__, rc, txt[:200])
        row["fail_reasons"].append("completion-gate-parse-error")
    # F: DELIVERED measure (runs live probes itself)
    t0 = time.time()
    rc, txt = run([sys.executable, "-I", "command-center/p2-wave/_measure_one_delivered.py", uid])
    dt = round(time.time() - t0, 1)
    tail = "\n".join(txt.strip().splitlines()[-14:])
    ok_f = (rc == 0 and ("SUCCESS:delivered " + uid) in txt)
    row["checks"]["F_delivered_measure"] = "ok SUCCESS:delivered" if ok_f else "FAIL rc=%d" % rc
    row["measure_tail"] = tail[:2000]
    row["measure_seconds"] = dt
    if not ok_f:
        row["fail_reasons"].append("delivered-measure:rc%d" % rc)
    # I: independent manifest sha recompute
    try:
        man = json.loads((REPO / ("command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json" % uid)).read_text(encoding="utf-8"))
        rows_m = [a for a in (man.get("artifacts") or []) if isinstance(a, dict) and a.get("unit_id") == uid]
        live_sha, _ = norm_sha(out)
        hit = [a for a in rows_m
               if str(a.get("path") or "").replace("\\", "/") == out_rel
               and str(a.get("sha256") or "") == live_sha
               and a.get("present") is True]
        row["checks"]["I_manifest_sha"] = "ok" if hit else (
            "FAIL live=%s rows=%s" % (live_sha[:12], [str(a.get("sha256"))[:12] for a in rows_m]))
        if not hit:
            row["fail_reasons"].append("manifest-sha-mismatch")
    except Exception as e:
        row["checks"]["I_manifest_sha"] = ("FAIL " + type(e).__name__ + ": " + str(e))[:200]
        row["fail_reasons"].append("manifest-read-error")
    row["verdict"] = "PASS-CLOSED" if not row["fail_reasons"] else "FAIL"
    summary[uid] = row
    emit(row)

(REPO / "_reviewer-w4s12/review_results.json").write_text(
    json.dumps(summary, indent=1), encoding="utf-8")
emit({"phase": "summary",
      "pass": [k for k, v in summary.items() if v["verdict"] == "PASS-CLOSED"],
      "fail": [k for k, v in summary.items() if v["verdict"] == "FAIL"]})
