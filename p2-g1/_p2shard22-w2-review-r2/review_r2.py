#!/usr/bin/env python3
"""Independent reviewer PASS 2, P2 wave-2 shard-22 (12 TST units).

Fresh implementation. Re-derives every DELIVERED-contract check from live
disk + live probe re-runs. Reviewer role: closers only. No receipt is
modified by THIS script; closure writes (if any unit is fully green) happen
in a separate, explicitly-reported step.
"""
import hashlib, json, os, re, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
OUT = REPO / "_p2shard22-w2-review-r2"
UNITS = ["TST-0060", "TST-0066", "TST-0068", "TST-0070", "TST-0081", "TST-0085",
         "TST-0088", "TST-0090", "TST-0091", "TST-0094", "TST-0100", "TST-0109"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT = 900

sys.path.insert(0, str(REPO / "platform" / "lib"))
import schema_resolver as sres   # noqa: E402
import receipt_schema_gate as rsg  # noqa: E402

BLOCKED_RE = re.compile(r"\"state\"\s*:\s*\"(BLOCKED|FAILED|SEVERED|TIMEOUT)\"")


def load_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


def norm_sha(path):
    b = Path(path).read_bytes()
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_probe_verbatim(cmd):
    """Run the recorded command string under bash so POSIX VAR=value prefixes
    are handled by the shell itself (verbatim semantics), from repo root."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(REPO / "command-center" / "p2-wave" / "seed-stage")
    bash = shutil.which("bash")
    argv = [bash, "-c", cmd] if bash else cmd
    shell = bash is None
    t0 = time.time()
    try:
        p = subprocess.run(argv, cwd=str(REPO), shell=shell, capture_output=True,
                           text=True, timeout=PROBE_TIMEOUT, errors="replace", env=env)
        out = (p.stdout or "")
        err = (p.stderr or "")
        return {"command": cmd, "exit": p.returncode,
                "secs": round(time.time() - t0, 1),
                "ok_marker": "SUCCESS:" in out,
                "tail": (out + err)[-400:]}
    except subprocess.TimeoutExpired:
        return {"command": cmd, "exit": "TIMEOUT", "secs": float(PROBE_TIMEOUT),
                "ok_marker": False, "tail": "killed at %ds" % PROBE_TIMEOUT}
    except Exception as e:
        return {"command": cmd, "exit": "SPAWN-ERROR", "secs": round(time.time() - t0, 1),
                "ok_marker": False, "tail": repr(e)[:400]}


def check_unit(uid, cat):
    v = {"id": uid, "checks": {}, "fail": []}
    ck = v["checks"]
    entry = next((e for e in cat.get("work_units", [])
                  if isinstance(e, dict) and e.get("id") == uid), None)
    ck["catalog_entry"] = entry is not None
    if entry is None:
        v["fail"].append("catalog-entry-missing")
        return v
    ck["catalog_output_path"] = bool(entry.get("output_path"))
    ck["catalog_output_schema"] = bool(entry.get("output_schema"))
    ck["catalog_dependencies"] = isinstance(entry.get("dependencies"), list)
    ck["catalog_description"] = bool(entry.get("question_or_target") or entry.get("description"))

    # --- artifact at catalog output_path
    ap = REPO / str(entry["output_path"])
    ck["artifact_exists"] = ap.is_file()
    raw = ap.read_bytes() if ap.is_file() else b""
    ck["artifact_nonempty"] = len(raw) > 0
    doc = load_json(ap) if ck["artifact_exists"] else None
    ck["artifact_parses"] = doc is not None
    ck["state_not_self_blocked"] = isinstance(doc, dict) and doc.get("state") not in NOT_DELIVERING
    ck["state_is_success"] = isinstance(doc, dict) and doc.get("state") == "SUCCESS"
    ck["failure_falsy"] = not (isinstance(doc, dict) and doc.get("failure"))
    blob = json.dumps(doc) if doc is not None else ""
    ck["no_self_declared_blocked_token"] = not BLOCKED_RE.search(blob)

    # --- sha pre-probe
    sha_pre = norm_sha(ap) if ap.is_file() else None

    # --- probes: re-run verbatim from PROBE-CMDS.json
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    pc = load_json(pdir / "PROBE-CMDS.json")
    ck["probe_cmds_present"] = isinstance(pc, list) and len(pc) > 0
    runs = [run_probe_verbatim(c) for c in pc] if isinstance(pc, list) else []
    ck["probes"] = runs
    ck["probes_exit0"] = bool(runs) and all(r["exit"] == 0 for r in runs)
    ck["probes_ok_marker"] = bool(runs) and all(r["ok_marker"] for r in runs)

    # --- sha post-probe (artifact byte-stability across probe re-runs)
    sha_post = norm_sha(ap) if ap.is_file() else None
    ck["artifact_stable_under_probes"] = sha_pre == sha_post and sha_pre is not None

    # --- manifest: every row recomputed and matched
    man = load_json(pdir / "UNIT-ARTIFACT-MANIFEST.json")
    ck["manifest_parses"] = man is not None
    row_bad = []
    if isinstance(man, dict):
        arts = man.get("artifacts", [])
        ck["manifest_expected_eq_present"] = man.get("expected") == man.get("present") == len(arts)
        prim = [a for a in arts if a.get("role") == "primary"]
        ck["manifest_primary_row"] = len(prim) == 1
        if prim:
            ck["manifest_primary_sha_ok"] = (prim[0].get("sha256") == sha_post)
        for a in arts:
            fp = REPO / str(a.get("path", ""))
            if not fp.is_file():
                row_bad.append("%s: missing" % a.get("path"))
                continue
            if norm_sha(fp) != a.get("sha256"):
                row_bad.append("%s: sha mismatch" % a.get("path"))
            if fp.stat().st_size != a.get("bytes"):
                row_bad.append("%s: bytes %d != declared %s" % (a.get("path"), fp.stat().st_size, a.get("bytes")))
        ck["manifest_all_rows_ok"] = not row_bad
        ck["manifest_row_errors"] = row_bad
    else:
        ck["manifest_expected_eq_present"] = False
        ck["manifest_primary_row"] = False
        ck["manifest_all_rows_ok"] = False

    # --- output_schema (catalog-declared, fail-closed resolver)
    errs = sres.validate_artifact(doc, str(entry["output_schema"]))
    ck["schema_ok"] = not errs
    ck["schema_errors"] = errs

    # --- admission corroboration (generic estate receipt.schema.json)
    aerr = rsg.validate_receipt(doc)
    ck["admission_ok"] = not aerr
    ck["admission_errors"] = aerr

    # --- closure validity
    rv = doc.get("reviewer") if isinstance(doc, dict) else None
    ck["existing_reviewer_verdict_pass"] = isinstance(rv, dict) and rv.get("verdict") == "PASS"
    ck["existing_reviewer_independent"] = isinstance(rv, dict) and rv.get("independent") is True
    ck["existing_reviewer_id"] = rv.get("reviewer_id") if isinstance(rv, dict) else None

    # --- substance
    ck["id_match"] = isinstance(doc, dict) and (doc.get("id") == uid or doc.get("unit_id") == uid)
    ck["min_bytes"] = len(raw) >= 2048

    hard = ["catalog_entry", "catalog_output_path", "catalog_output_schema",
            "catalog_dependencies", "catalog_description", "artifact_exists",
            "artifact_nonempty", "artifact_parses", "state_not_self_blocked",
            "state_is_success", "failure_falsy", "no_self_declared_blocked_token",
            "probe_cmds_present", "probes_exit0", "probes_ok_marker",
            "artifact_stable_under_probes", "manifest_parses",
            "manifest_expected_eq_present", "manifest_primary_row",
            "manifest_primary_sha_ok", "manifest_all_rows_ok", "schema_ok",
            "existing_reviewer_verdict_pass", "existing_reviewer_independent",
            "id_match", "min_bytes"]
    for k in hard:
        if ck.get(k) is not True:
            v["fail"].append("check-false:" + k)
    if v["fail"]:
        v["verdict"] = "FAIL"
    else:
        v["verdict"] = "ELIGIBLE-CONFIRM"
    return v


def main():
    cat = load_json(REPO / "command-center" / "WORK-UNIT-CATALOG.json") or {}
    results = [check_unit(u, cat) for u in UNITS]
    out = {"reviewer_id": "claude-opus-5-5-independent-reviewer-shard22-w2-r2-2026-10-26",
           "run_at": now_iso(), "mode": "verify-pass2", "results": results}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verify_out_r2.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("UNIT       VERDICT          fails")
    for r in results:
        print("%-10s %-16s %s" % (r["id"], r["verdict"], ";".join(r["fail"])[:120]))
    print("probe_exit_fail:", [r["id"] for r in results if not r["checks"].get("probes_exit0")])
    print("schema_fail:", [r["id"] for r in results if not r["checks"].get("schema_ok")])
    print("manifest_fail:", [r["id"] for r in results if not r["checks"].get("manifest_all_rows_ok")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
