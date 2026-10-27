import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
import receipt_schema_gate as rsg  # noqa: E402
import schema_resolver as sres  # noqa: E402

OUT = REPO / "_p2shard19-w2-review"
v = json.loads((OUT / "verify_out.json").read_text(encoding="utf-8"))
cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
entry = {e.get("id"): e for e in cat["work_units"]}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


report = {"reviewer_id": "claude-opus-5-5-independent-reviewer-shard19-w2-2026-10-25",
          "wave": "p2-wave-2 shard 19", "closed_at": now_iso(),
          "receipts_modified": False,
          "note": ("Reviewer verdicts only; receipts left in builder BLOCKED state per the "
                   "unit contract (ANY failing check -> verdict FAIL, receipt unchanged)."),
          "units": {}}

for uid in sorted(v):
    u = v[uid]
    ap = REPO / str(entry[uid]["output_path"])
    parsed = json.loads(ap.read_text(encoding="utf-8"))
    errs = sres.validate_artifact(parsed, entry[uid]["output_schema"])
    # unique error classes (strip volatile detail after first colon)
    classes = []
    for e in errs:
        key = e.split(": ", 1)[-1]
        short = key if key.startswith("<root>") else (e.split("/")[0] + ": " + key.split(" is a required property")[0])
        classes.append(e[:150])
    checks = {
        "artifact_exists_nonempty_parses": bool(u.get("artifact_exists") and u.get("artifact_bytes", 0) > 0
                                                and u.get("artifact_parses")),
        "not_self_declared_blocked_failed": not bool(u.get("self_decl_top")),
        "probes_rerun_exit0_reviewer": bool(u.get("probes_ok")),
        "manifest_sha256_crlf_normalized_match": bool(u.get("sha_ok_manifest")),
        "receipt_artifact_rows_match_disk": bool(u.get("sha_ok_receipt")),
        "min_bytes_threshold_respected": bool(u.get("min_bytes_ok")),
        "output_schema_validates": bool(u.get("schema_ok")),
        "receipt_admission_clean_pre_closure": not bool(u.get("admission_errors")),
    }
    failing = [k for k, ok in checks.items() if not ok]
    verdict = "FAIL" if failing else "PASS"
    reasons = []
    if u.get("self_decl_top"):
        reasons.append("self-declared not-delivering at artifact top level: "
                       + json.dumps(u["self_decl_top"])[:300])
    if not u.get("schema_ok"):
        reasons.append(f"output_schema '{entry[uid]['output_schema']}' validation: "
                       f"{len(errs)} errors; first: {errs[0][:220]}")
    if not u.get("sha_ok_manifest"):
        reasons.append("UNIT-ARTIFACT-MANIFEST.json row does not match live artifact")
    report["units"][uid] = {
        "verdict": verdict,
        "failing_checks": failing,
        "schema_error_count": len(errs),
        "probe_reRuns": [{"script": p["script"], "exit": p["exit"], "marker": p["ok_marker"]}
                         for p in u.get("probes", [])],
        "receipt_state_before": u.get("receipt_state"),
        "receipt_state_after": json.loads(
            (REPO / "command-center" / "receipts" / (uid + ".json")).read_text(encoding="utf-8")
        ).get("state"),
        "reasons": reasons,
    }

(OUT / "closure_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
for uid, x in report["units"].items():
    print(uid, x["verdict"], "| schema_errs:", x["schema_error_count"],
          "| failing:", ",".join(x["failing_checks"]))
print()
print("receipts_modified:", report["receipts_modified"])
