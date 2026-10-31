"""Emit REVIEW-RETURN.json for INDEPENDENT REVIEWER wave 3 shard 12 from verify_battery.json."""
import json, time
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
b = json.loads((REPO/"_reviewer-w3-shard12/verify_battery.json").read_text(encoding="utf-8"))

untouched = {}
units = {}
for uid, r in b["results"].items():
    pre = r.get("pre_state") or {}
    untouched[uid] = {
        "sha256_lf": pre.get("sha256_lf"),
        "bytes": pre.get("bytes"),
        "mtime": pre.get("mtime"),
        "manifest_receipt_row_match": r["D"]["receipt_row_match"],
    }
    B = r["B"]; C = r["C"]; D = r["D"]; E = r["E"]
    failing = []
    if B["resolver_errors"] > 0:
        failing.append(
            "output_schema invalid: %d errors against catalog-declared %s via program resolver "
            "(platform/lib/schema_resolver.validate_artifact, AST_INTEGRATE_ROOT=p2-g1); first: %s"
            % (B["resolver_errors"], r["output_path"] and "command-center/schema/receipt.schema.json", B["resolver_first3"][0] if B["resolver_first3"] else "")
        )
    if B["admission"].startswith("REJECT"):
        failing.append("admission gate REJECT: %s" % B["admission"])
    if not D["receipt_row_match"]:
        failing.append("manifest receipt-row sha mismatch")
    if D["rows_drift"]:
        failing.append("manifest supporting-row drift: %s" % ", ".join(D["rows_drift"]))
    if not C.get("all_exit0"):
        failing.append("live probe re-run not all exit 0")
    green = []
    if r["A"].get("artifact") == "ok":
        green.append("artifact exists/non-empty/parses; state=%s; sentinel present" % r["A"].get("state"))
    if C.get("all_exit0"):
        green.append("probes %d/%d re-run exit 0 with pass=true" % (len(C.get("probes") or []), len(C.get("probes") or [])))
    if D["receipt_row_match"]:
        green.append("manifest receipt-row sha matches live (CRLF->LF)")
    if E.get("valid_existing_closure"):
        green.append("prior closure fields present (state=SUCCESS, reviewer PASS+independent) but NOT confirmable over a schema-invalid receipt")
    units[uid] = {
        "verdict": "FAIL" if failing else "PASS",
        "state": E.get("state"),
        "awaiting_review": False,
        "schema_errors": B["resolver_errors"],
        "probes_all_exit0": C.get("all_exit0"),
        "manifest_receipt_row_match": D["receipt_row_match"],
        "manifest_all_rows_match": (D["rows_match"] == D["rows_total"]),
        "profile_required_fields_missing": B["profile_missing"],
        "green_legs": "; ".join(green),
        "failing_check": failing,
        "full_schema_errors": B["full_errors"],
    }

ret = {
    "role": "INDEPENDENT REVIEWER wave 3 shard 12",
    "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "reviewer": "claude-opus-5-5-ind-reviewer-w3-shard12-2026-10-26",
    "scope": b["units"],
    "did_not_build": True,
    "instruments": {
        "schema": "platform/lib/schema_resolver.validate_artifact (program resolver, AST_INTEGRATE_ROOT=p2-g1) on the catalog output_schema string, cross-checked by command-center/receipt_validate.py admission (Layer-1 receipt_schema_gate C2)",
        "probes": "direct sys.executable -B per recorded named-probe command, cwd=p2-g1, PYTHONDONTWRITEBYTECODE=1, JSON pass-flag parsed from stdout plus SUCCESS: line",
        "manifest": "sha256 with CRLF->LF normalization of every UNIT-ARTIFACT-MANIFEST.json row vs live bytes",
        "controls": "counterfactual receipts IMP-0001/IMP-0021/IMP-0067 validate with ZERO resolver errors and negative mutation control (unit_id removed) fires 18 errors under identical env - the schema is in force and satisfiable; these 12 receipts are stale/nonconforming, not victims of an unmeetable schema",
    },
    "receipts_untouched_proof": untouched,
    "units": units,
    "summary": {
        "pass": [u for u, v in units.items() if v["verdict"] == "PASS"],
        "fail": [u for u, v in units.items() if v["verdict"] == "FAIL"],
        "headline": "0/12 PASS, 12/12 FAIL on the single output_schema leg (resolver errors 4-34 each, admission REJECT all); probes 24/24 exit 0, manifest receipt-rows 12/12 match live; receipts byte-untouched",
        "closure_action": "no receipts modified; all 12 keep their pre-existing (self-attested, unverifiable) SUCCESS/PASS fields; a builder receipt re-anchor to the current receipt_core schema is required, then fresh independent review",
        "notable": {
            "IMP-0264": "receipt evidence claims kernel_bytes=13600/kernel_sha256=b28ea981... but the live manifest-pinned kernel.py is 6446 bytes/66780ec1... - stale evidence vs the delivered implementation",
            "IMP-0304": "3 of 8 manifest supporting rows drifted vs live (tools/council/vote/weights.py, tools/council/__init__.py, tools/council/vote/__init__.py) beyond CRLF normalization - genuine content drift",
        },
    },
}

dest = REPO/"_reviewer-w3-shard12/REVIEW-RETURN.json"
dest.write_text(json.dumps(ret, indent=1), encoding="utf-8")
print("wrote", dest)
print("pass:", ret["summary"]["pass"])
print("fail:", len(ret["summary"]["fail"]), "units")
