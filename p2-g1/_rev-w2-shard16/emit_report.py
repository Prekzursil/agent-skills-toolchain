#!/usr/bin/env python3
"""Independent reviewer w2s16 - final report emitter (2026-10-26).

Merges readonly-sweep.json + probe-rerun.json into the final reviewer report.
Verdict rule (fail-closed): PASS requires ALL of
  artifact present/non-empty/parses + not self-blocked + receipt-core SUCCESS gate
  + manifest sha match (CRLF->LF normalized) + live probes rc=0 with completion markers
  + output_schema valid.
ANY fail -> FAIL, receipts unchanged. Also proves receipts untouched via manifest shas.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    sweep = json.loads((HERE / "readonly-sweep.json").read_text(encoding="utf-8"))
    probes = json.loads((HERE / "probe-rerun.json").read_text(encoding="utf-8"))
    units = []
    n_pass = n_fail = 0
    for uid in sorted(sweep):
        e = sweep[uid]
        pr = probes[uid]
        fails = list(e.get("fail", [])) + list(pr.get("fail", []))
        # receipts unchanged: live sha still equals the builder-recorded manifest sha
        sha_ok = e.get("manifest_sha") == e.get("live_sha256")
        # reviewer-closure provenance (verified by reviewer against receipts directly):
        # 11/12 reviewer_id == the unit's own probe2 script (self-closure); REL-0001 is a
        # stale 2026-08-21 external import. Neither is a valid independent closure under
        # "only the independent reviewer closes". Recorded as a second fail reason; does
        # not change verdicts (schema already fails all 12).
        rid = (e.get("reviewer") or {}).get("reviewer_id") or ""
        own_probe = uid in rid
        stale_external = ("2026-08-21" in rid) or ("C5" in rid)
        if own_probe:
            fails.append("reviewer-closure-not-independent: reviewer_id is the unit's own probe script (self-closure): " + rid)
        elif stale_external:
            fails.append("reviewer-closure-stale-external: " + rid)
        verdict = "PASS" if (not fails and sha_ok) else "FAIL"
        if verdict == "PASS":
            n_pass += 1
        else:
            n_fail += 1
        units.append({
            "unit_id": uid,
            "output_path": e.get("output_path"),
            "state": e.get("state"),
            "reviewer_block": e.get("reviewer"),
            "checks": {
                "artifact-present-nonempty-parses": "parses-dict" in e.get("checks", {}),
                "no-failure-block": "no-failure-block" in e.get("checks", {}),
                "receipt-core-fields-present": "receipt-core-success-gate" in e.get("checks", {}),
                "valid-independent-closure": not (own_probe or stale_external),
                "manifest-sha-match-crlf-normalized": sha_ok,
                "probes-live-rc0": not pr.get("fail"),
                "output_schema-valid": "output_schema-valid" in e.get("checks", {}),
            },
            "probe_runs": pr.get("probes", []),
            "schema_error_count": e.get("schema_error_count", 0),
            "schema_errors_first": e.get("schema_errors_first", []),
            "live_sha256": e.get("live_sha256"),
            "manifest_sha256": e.get("manifest_sha"),
            "verdict": verdict,
            "fail_reasons": fails if fails else (
                [] if sha_ok else [f"manifest-sha-mismatch declared={e.get('manifest_sha')} live={e.get('live_sha256')}"]
            ),
        })
    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reviewer_id": "claude-opus-5-5 workflow-reviewer w2s16 2026-10-26",
        "role": "independent-reviewer",
        "shard": "w2s16",
        "method": {
            "artifact_checks": "exists + non-empty + json.loads dict + state not in {BLOCKED,FAILED}",
            "receipt_core_gate": "state=SUCCESS requires reviewer.verdict=PASS and reviewer.independent=true",
            "sha": "sha256 of raw bytes with CRLF normalized to LF, vs probes/<id>/UNIT-ARTIFACT-MANIFEST.json row at output_path",
            "probes": "PYTHONDONTWRITEBYTECODE=1 python3 -B <probe> from repo root, rc=0 + terminal completion marker, no FAILED: line",
            "schema": "jsonschema validator_for(schema) against catalog output_schema file",
            "receipts_modified": False,
            "closure_action": "none - any failing check forbids closure; receipts unchanged",
            "both_states_control": "validator returned 0 errors on shard-18 PASS receipts RES-0131/0132/0137/0148 (instrument can go green)",
        },
        "summary_counts": {"pass": n_pass, "fail": n_fail, "total": len(units)},
        "units": units,
    }
    (HERE / "reviewer-report-w2s16-2026-10-26.json").write_text(
        json.dumps(report, indent=1), encoding="utf-8"
    )
    for u in units:
        st = u["verdict"]
        why = "; ".join(u["fail_reasons"][:2]) if u["fail_reasons"] else ""
        print(f"{u['unit_id']}: {st} {why}")
    print(f"SUMMARY pass={n_pass} fail={n_fail} total={len(units)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
