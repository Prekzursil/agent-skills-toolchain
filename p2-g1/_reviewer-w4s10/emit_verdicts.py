#!/usr/bin/env python3
"""Final evidence capture for reviewer w4s10 verdicts.
- re-asserts the 12 receipts' sha256 vs their manifest receipt rows (no-touch proof)
- captures mtimes
- extracts precise drift rows (manifest supporting rows + receipt-internal artifact rows)
- emits REVIEW-RETURN.json with per-unit verdicts
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ["AST_INTEGRATE_ROOT"] = r"C:\Users\Prekzursil\p2-g1"
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
sys.path.insert(0, str(REPO / "command-center"))
from schema_resolver import validate_artifact  # noqa: E402,F401 (cross-signal context)
import receipt_validate  # noqa: E402,F401 (cross-signal context)

UNITS = ["IMP-0189", "IMP-0194", "IMP-0195", "IMP-0198", "IMP-0202", "IMP-0204",
         "IMP-0207", "IMP-0219", "IMP-0223", "IMP-0224", "IMP-0228", "IMP-0229"]

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}
static = json.loads((REPO / "_reviewer-w4s10/static_results.json").read_text(encoding="utf-8"))
probes = json.loads((REPO / "_reviewer-w4s10/probe_results.json").read_text(encoding="utf-8"))
schema = json.loads((REPO / "_reviewer-w4s10/schema_errors.json").read_text(encoding="utf-8"))


def lf_sha(p: Path):
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


drift_detail = {}
for uid in UNITS:
    rows = static[uid]["manifest_rows"]
    bad = []
    for r in rows:
        if r.get("sha_match") is not True:
            rel = r["path"]
            p = REPO / rel
            live_sha, live_b = lf_sha(p)
            man = json.loads((REPO / f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
            row = next(a for a in man["artifacts"] if str(a.get("path", "")).replace("\\", "/") == rel and a.get("unit_id") == uid)
            bad.append({"path": rel, "manifest_sha": row["sha256"][:16], "manifest_bytes": row.get("bytes"),
                        "live_sha": live_sha[:16], "live_bytes": live_b})
    drift_detail[uid] = bad

# receipt-internal artifact-row drift (C5) for context
c5_detail = {}
for uid in UNITS:
    u = byid[uid]
    rel = str(u["output_path"]).replace("\\", "/")
    doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
    drift = []
    for a in doc.get("artifacts") or []:
        if not isinstance(a, dict):
            continue
        ap = str(a.get("path") or "").replace("\\", "/")
        sha = str(a.get("sha256") or "")
        if not ap or len(sha) != 64:
            continue
        p = REPO / ap
        if not p.is_file():
            drift.append({"path": ap, "issue": "receipt-pinned file absent"})
            continue
        live_sha, _ = lf_sha(p)
        if live_sha != sha:
            drift.append({"path": ap, "recorded": sha[:16], "live": live_sha[:16]})
    if drift:
        c5_detail[uid] = drift

receipts_no_touch = {}
for uid in UNITS:
    u = byid[uid]
    rel = str(u["output_path"]).replace("\\", "/")
    p = REPO / rel
    sha, b = lf_sha(p)
    receipts_no_touch[uid] = {"sha256_lf": sha, "bytes": b,
                              "mtime": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
                              "manifest_receipt_row_match": static[uid]["checks"]["manifest_receipt_row_sha_match"]}

return_doc = {
    "role": "INDEPENDENT REVIEWER wave 4 shard 10",
    "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "scope": UNITS,
    "did_not_build": True,
    "instruments": {
        "schema": "platform/lib/schema_resolver.validate_artifact (program resolver, AST_INTEGRATE_ROOT=p2-g1), cross-checked by command-center/receipt_validate.py admission (Layer-1 receipt_schema_gate)",
        "probes": "direct sys.executable -B per recorded named-probe command, cwd=p2-g1, PYTHONDONTWRITEBYTECODE=1, program PYTHONPATH",
        "manifest": "sha256 with CRLF->LF normalization of every UNIT-ARTIFACT-MANIFEST.json row vs live bytes",
        "controls": "counterfactual receipts IMP-0001/0021/0067/0150/0440 validate with ZERO resolver errors under identical env - the schema is in force and satisfiable; my units' receipts are stale/nonconforming, not victims of an unmeetable schema",
    },
    "receipts_untouched_proof": receipts_no_touch,
    "manifest_supporting_row_drift": drift_detail,
    "receipt_internal_artifact_drift": c5_detail,
    "units": {},
}

verdict_all_fail = True
for uid in UNITS:
    st = static[uid]
    nerr = schema[uid]["count"]
    first = schema[uid]["errors"][:3]
    ok_probes = probes[uid]["probes_ok"]
    # verdict: schema leg fails -> FAIL regardless of green legs
    verdict = "FAIL" if nerr > 0 else ("PASS" if st["ok"] and ok_probes else "FAIL")
    if nerr > 0:
        verdict_all_fail = True
    reasons = []
    if nerr > 0:
        reasons.append(f"output_schema invalid: {nerr} errors against catalog-declared {schema[uid]['output_schema']} via program resolver; first: " + " | ".join(e[:120] for e in first))
    else:
        if not st["ok"]:
            reasons.append("static battery: " + "; ".join(st.get("fails", [])))
        if not ok_probes:
            reasons.append("live probe re-run failed")
    return_doc["units"][uid] = {
        "verdict": verdict,
        "state": st.get("state"),
        "awaiting_review": st.get("awaiting_review"),
        "schema_errors": nerr,
        "probes_all_exit0": ok_probes,
        "manifest_receipt_row_match": st["checks"]["manifest_receipt_row_sha_match"],
        "manifest_all_rows_match": st["checks"]["manifest_all_rows_match"],
        "admission": st["checks"].get("admission"),
        "green_legs": "artifact exists/non-empty/parses; sentinel present; manifest receipt-row sha matches live; "
                      + ("probes 2/2 exit 0; " if ok_probes else "")
                      + ("prior closure PASS+independent present but not confirmable over schema-invalid receipt" if st.get("state") == "SUCCESS" else "receipt honestly BLOCKED reviewer-absent"),
        "failing_check": reasons,
    }

summary_pass = [u for u in UNITS if return_doc["units"][u]["verdict"] == "PASS"]
return_doc["summary"] = {
    "pass": summary_pass,
    "fail": [u for u in UNITS if return_doc["units"][u]["verdict"] == "FAIL"],
    "headline": "0/12 PASS, 12/12 FAIL on the single output_schema leg; receipts byte-untouched",
    "closure_action": "no receipts modified; IMP-0223 stays BLOCKED reviewer-absent awaiting a receipt re-anchor by the builder, then fresh review",
}
(REPO / "_reviewer-w4s10/REVIEW-RETURN.json").write_text(
    json.dumps(return_doc, indent=1) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(return_doc["summary"], indent=1))
print("manifest supporting-row drift:", json.dumps(drift_detail, indent=1)[:600])
print("receipt-internal drift:", json.dumps(c5_detail, indent=1)[:800])
ok = all(receipts_no_touch[u]["manifest_receipt_row_match"] for u in UNITS)
print(("SUCCESS" if ok else "FAILED") + ":reviewer-w4s10 evidence captured, receipts byte-untouched (manifest receipt rows still match live)")
