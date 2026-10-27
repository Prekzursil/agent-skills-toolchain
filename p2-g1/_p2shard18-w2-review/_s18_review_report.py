#!/usr/bin/env python3
"""Wave-2 shard-18 INDEPENDENT reviewer report (12 units).

Re-measures every check live: artifact existence/parse/self-block, output_schema
validation via the repo resolver, manifest sha256 (CRLF-normalized) vs live bytes,
and a full live re-run of the named probes from SUBAGENT-RETURN.json.
PASS -> all checks hold (already-closed receipts stay SUCCESS, open ones close).
FAIL -> receipts untouched; precise failing checks recorded here.
"""
import hashlib, json, sys
from pathlib import Path
WS = Path("C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(WS / "command-center/p2-wave"))
import _p2lib as P
import _measure_one_delivered as M

CAT = json.load(open(WS / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
BYID = {u["id"]: u for u in CAT["work_units"]}
UNITS = ["RES-0112","RES-0114","RES-0128","RES-0131","RES-0132","RES-0137",
         "RES-0140","RES-0141","RES-0144","RES-0148","RES-0149","RES-0150"]
BAD = {"BLOCKED","FAILED","SEVERED","TIMEOUT"}
report = []
for uid in UNITS:
    e = BYID[uid]
    rec = {"unit_id": uid, "verdict": "PASS", "fail_reasons": []}
    checks = {}
    out = WS.joinpath(*e["output_path"].split("/"))
    checks["artifact_exists"] = out.is_file()
    raw = out.read_bytes() if out.is_file() else b""
    checks["artifact_nonempty"] = len(raw) > 0
    doc = None
    try:
        doc = json.loads(raw.decode("utf-8"))
        checks["artifact_parses"] = True
    except Exception:
        checks["artifact_parses"] = False
    checks["artifact_not_self_blocked"] = not (isinstance(doc, dict) and str(doc.get("state") or "").upper() in BAD)
    # schema
    errs = P.validate(doc, e["output_schema"]) if doc is not None else ["artifact-unreadable"]
    checks["output_schema_errors"] = len(errs)
    # manifest sha (CRLF-normalized)
    man = json.loads((WS / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
    nsha = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == uid and a.get("role") == "primary"
            and a.get("path","").replace("\\","/") == e["output_path"]]
    checks["manifest_exists"] = True
    checks["manifest_sha_match"] = any(a.get("sha256") == nsha and a.get("present") is True for a in rows)
    rec["manifest_sha_live"] = nsha
    rec["manifest_sha_declared"] = rows[0].get("sha256") if rows else None
    rec["schema_errors_first"] = [str(x)[:300] for x in errs[:5]]
    # probes: live re-run, same selection the delivery measure uses
    probe_dir = WS / "command-center/p2-wave/probes" / uid
    ret = json.loads((probe_dir / "SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
    cmds = M.probe_commands(uid, ret, probe_dir)
    checks["probe_scripts_found"] = len(cmds)
    probe_rows = []
    probes_ok = True
    for cmd in cmds:
        code, tail = M.run_cmd(cmd)
        probes_ok = probes_ok and code == 0
        probe_rows.append({"command": cmd, "exit_code": code, "tail": tail[-400:]})
    checks["probes_all_exit_zero"] = probes_ok
    rec["probes"] = probe_rows
    # receipt
    rp = WS / "command-center/receipts" / f"{uid}.json"
    r = json.loads(rp.read_text(encoding="utf-8"))
    checks["receipt_exists"] = True
    rev = r.get("reviewer", {})
    already = r.get("state") == "SUCCESS" and rev.get("verdict") == "PASS" and rev.get("independent") is True
    checks["closure_fields_valid_or_open"] = already or (r.get("state") == "BLOCKED" and (r.get("failure") or {}).get("classification") == ["reviewer-absent"])
    rec["receipt_state_before"] = r.get("state")
    rec["already_closed"] = already
    rec["checks"] = checks
    fail = []
    if not checks["artifact_exists"]: fail.append("artifact-missing at " + e["output_path"])
    if not checks["artifact_nonempty"]: fail.append("artifact-empty")
    if not checks["artifact_parses"]: fail.append("artifact-unparseable")
    if not checks["artifact_not_self_blocked"]: fail.append("artifact-self-declared-BLOCKED/FAILED")
    if checks["output_schema_errors"] > 0: fail.append(f"output_schema_errors={len(errs)}: " + " | ".join(str(x) for x in errs))
    if not checks["manifest_sha_match"]: fail.append("manifest-sha-mismatch (CRLF-normalized)")
    if not checks["probes_all_exit_zero"]: fail.append("probe-nonzero-exit: " + str([(p['exit_code'], p['command']) for p in probe_rows if p['exit_code'] != 0]))
    if not checks["closure_fields_valid_or_open"]: fail.append(f"receipt-state-unexpected:{r.get('state')}")
    rec["fail_reasons"] = fail
    rec["verdict"] = "PASS" if not fail else "FAIL"
    report.append(rec)
outp = WS / "_p2shard18-w2-review" / "reviewer-report.json"
outp.write_text(json.dumps(report, indent=1), encoding="utf-8")
for rec in report:
    print(rec["verdict"], rec["unit_id"], ("OK" if not rec["fail_reasons"] else "; ".join(rec["fail_reasons"])[:220]))
n_pass = sum(1 for r in report if r["verdict"] == "PASS")
print(f"SUMMARY pass={n_pass} fail={len(report)-n_pass} report={outp}")
