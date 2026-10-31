#!/usr/bin/env python3
"""Independent reviewer battery, wave-3 shard 24 (r2 re-derivation).

For each unit: catalog conformance, receipt existence/parse/state, live probe
re-run (exit 0), manifest sha256 (CRLF->LF) match, resolver schema validation,
reviewer-closure rule, and an independent content contradiction scan.
Never writes to receipts. Output: verdicts.json next to this script.
"""
from __future__ import annotations
import hashlib, importlib.util, json, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
UNITS = ["TST-0206", "TST-0215", "TST-0219", "TST-0221",
         "TST-0223", "TST-0227", "TST-0230", "TST-0233"]
PROBE_ROOT = REPO / "command-center" / "p2-wave" / "probes"
BAD_TEST = {"FAIL", "ERROR", "SKIP", "NOT-RUN"}
OPEN_STATES = {"open", "new", "unresolved", "", "none", "investigating"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


p = REPO / "platform" / "lib" / "schema_resolver.py"
sys.path.insert(0, str(p.parent))
spec = importlib.util.spec_from_file_location("schema_resolver_r2", p)
mod = importlib.util.module_from_spec(spec)
sys.modules["schema_resolver_r2"] = mod
spec.loader.exec_module(mod)
RESOLVER = mod

cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
IDX = {e["id"]: e for e in cat["work_units"]}

out = {"shard": "wave 3 shard 24 review (r2, independent re-derivation)",
       "reviewer_id": "claude-opus-5-5 wf resume review:w3s24 r2",
       "reviewed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
       "verdicts": {}}

for uid in UNITS:
    R = {"unit_id": uid}
    checks = {}
    try:
        entry = IDX[uid]
        R["catalog_present"] = True
        R["output_path"] = entry["output_path"]
        R["output_schema"] = entry["output_schema"]
        R["catalog_has_probes_field"] = "probes" in entry
        R["owner_approval_required"] = entry.get("owner_approval_required", False)
    except KeyError:
        R["catalog_present"] = False
        R["verdict"] = "FAIL"
        R["fail_reason"] = "no catalog entry"
        out["verdicts"][uid] = R
        continue

    rp = REPO / entry["output_path"]
    before = rp.read_bytes() if rp.is_file() else b""
    R["receipt"] = {"path": entry["output_path"], "exists": rp.is_file(),
                    "bytes": len(before)}
    doc = None
    if before:
        try:
            doc = json.loads(before.decode("utf-8"))
            R["receipt"]["parses"] = True
        except Exception as e:
            R["receipt"]["parses"] = False
            R["receipt"]["parse_error"] = str(e)[:300]
    R["state"] = doc.get("state") if doc else None
    R["sentinel"] = (doc.get("sentinel") if doc else "") or ""
    R["self_blocked_or_failed"] = bool(
        (doc and doc.get("state") in ("BLOCKED", "FAILED"))
        or R["sentinel"].startswith("FAILED:"))

    # --- probes: manifest named-probe rows, re-run live ---
    pd = PROBE_ROOT / uid
    mf_path = pd / "UNIT-ARTIFACT-MANIFEST.json"
    R["manifest_present"] = mf_path.is_file()
    probe_rows, mf_rows = [], []
    if mf_path.is_file():
        mf = json.loads(mf_path.read_text(encoding="utf-8"))
        for a in mf.get("artifacts", []):
            mf_rows.append({"path": a.get("path"), "role": a.get("role"),
                            "sha256": a.get("sha256"), "bytes": a.get("bytes"),
                            "present_now": (REPO / a["path"]).is_file() if a.get("path") else False})
        probe_rows = [a for a in mf.get("artifacts", []) if a.get("role") == "named-probe"]
    R["manifest_rows"] = mf_rows
    probes = {}
    for a in probe_rows:
        sp = REPO / a["path"]
        name = Path(a["path"]).name
        t0 = time.time()
        try:
            pr = subprocess.run([sys.executable, str(sp)], cwd=str(pd),
                                capture_output=True, text=True, timeout=240)
            rc, so, se = pr.returncode, pr.stdout[-4000:], pr.stderr[-4000:]
        except subprocess.TimeoutExpired:
            rc, so, se = 124, "", "TIMEOUT 240s"
        probes[name] = {"rc": rc, "secs": round(time.time() - t0, 1),
                        "stdout_tail": so, "stderr_tail": se}
    R["probes_rerun"] = probes
    checks["probes_exit0"] = bool(probe_rows) and all(v["rc"] == 0 for v in probes.values())

    after = rp.read_bytes() if rp.is_file() else b""
    R["receipt_untouched_by_review"] = before == after

    # --- sha256 checks ---
    if before:
        raw_sha, lfn_sha = sha(before), sha(lf(before))
        R["receipt_sha256_raw"] = raw_sha
        R["receipt_sha256_lf"] = lfn_sha
        prim = [a for a in mf_rows if a["role"] == "primary" and a["path"] == entry["output_path"]]
        R["manifest_primary_row"] = prim[0] if prim else None
        if prim:
            ms = prim[0]["sha256"]
            R["sha_match_mode"] = "lf" if ms == lfn_sha else ("raw" if ms == raw_sha else "MISMATCH")
            checks["manifest_sha_match"] = R["sha_match_mode"] in ("lf", "raw")
        else:
            R["sha_match_mode"] = "NO-PRIMARY-ROW"
            checks["manifest_sha_match"] = False
        row_results = {}
        for a in mf_rows:
            ap = REPO / a["path"]
            if ap.is_file():
                d2 = ap.read_bytes()
                row_results[a["path"]] = ("lf" if a["sha256"] == sha(lf(d2)) else
                                          ("raw" if a["sha256"] == sha(d2) else "MISMATCH"))
            else:
                row_results[a["path"]] = "MISSING"
        R["manifest_all_rows_sha_status"] = row_results
        checks["all_manifest_rows_present_and_match"] = all(
            v not in ("MISMATCH", "MISSING") for v in row_results.values())
    else:
        checks["manifest_sha_match"] = False

    # --- schema via program resolver ---
    if doc is not None:
        try:
            errs = RESOLVER.validate_artifact(doc, entry["output_schema"])
            R["schema_errors"] = errs
            checks["schema_valid"] = len(errs) == 0
        except Exception as e:
            R["schema_errors"] = ["resolver exception: " + str(e)]
            checks["schema_valid"] = False
    else:
        R["schema_errors"] = ["receipt missing or unparseable"]
        checks["schema_valid"] = False

    # --- reviewer closure rule + independent content contradiction scan ---
    if doc and doc.get("state") == "SUCCESS":
        rv = doc.get("reviewer") or {}
        R["reviewer_verdict"] = rv.get("verdict")
        R["reviewer_independent"] = rv.get("independent")
        checks["reviewer_pass_independent"] = (rv.get("verdict") == "PASS"
                                               and rv.get("independent") is True)
        cont = {}
        bad_defects = [d for d in doc.get("defects", [])
                       if d.get("severity") in ("P0", "P1")
                       and str(d.get("status", "OPEN")).lower() in OPEN_STATES]
        cont["open_p0p1_defects"] = [{"id": d.get("id"), "severity": d.get("severity"),
                                      "status": d.get("status"),
                                      "title": str(d.get("title", ""))[:200]}
                                     for d in bad_defects]
        bad_tests = [{"id": t.get("id"), "result": t.get("result")}
                     for t in doc.get("tests", []) if t.get("result") in BAD_TEST]
        cont["bad_test_rows"] = bad_tests
        bad_nc = [{"id": n.get("id")} for n in doc.get("negative_controls", [])
                  if n.get("fired_on_bad_state") is False
                  or n.get("silent_on_good_state") is False]
        cont["bad_negative_controls"] = bad_nc
        mreg = doc.get("manifest_registration") or {}
        cont["manifest_registration"] = mreg
        cons = doc.get("downstream_consumers", [])
        cont["consumers_executed"] = [{"id": c.get("id"), "executed": c.get("executed"),
                                       "read_ok": c.get("read_ok")} for c in cons]
        cont["any_consumer_executed_ok"] = any(c.get("executed") and c.get("read_ok")
                                               for c in cons)
        cont["evidence_count"] = len(doc.get("evidence", []))
        R["content_scan"] = cont
        checks["no_open_p0p1_defects"] = len(bad_defects) == 0
        checks["no_bad_test_rows"] = len(bad_tests) == 0
        checks["negative_controls_both_states"] = len(bad_nc) == 0
        checks["manifest_registered"] = mreg.get("registered") is True
        checks["consumer_executed_ok"] = cont["any_consumer_executed_ok"]
        checks["evidence_two_signals"] = cont["evidence_count"] >= 2
    else:
        checks["reviewer_pass_independent"] = False
        R["reviewer_verdict"] = None
        R["reviewer_independent"] = None

    checks["receipt_exists_nonempty_parses"] = bool(before) and R["receipt"].get("parses") is True
    checks["not_self_blocked"] = not R["self_blocked_or_failed"]
    R["checks"] = checks
    failed = [k for k, v in checks.items() if not v]
    R["failed_checks"] = failed
    R["verdict"] = "PASS" if not failed else "FAIL"
    if failed:
        R["fail_reason"] = "failing checks: " + ", ".join(failed)
    out["verdicts"][uid] = R

out["summary"] = {
    "pass": sum(1 for v in out["verdicts"].values() if v["verdict"] == "PASS"),
    "fail": sum(1 for v in out["verdicts"].values() if v["verdict"] == "FAIL"),
}
(HERE / "verdicts.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps(out["summary"]))
for uid, v in out["verdicts"].items():
    print(uid, v["verdict"], "| failed:", ",".join(v.get("failed_checks", [])) or "-")
