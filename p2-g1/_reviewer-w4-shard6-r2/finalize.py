import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
OUT = REPO / "_reviewer-w4-shard6-r2"
bat = json.loads((OUT / "battery_out.json").read_text(encoding="utf-8"))
cens = json.loads((OUT / "census_out.json").read_text(encoding="utf-8"))

UNITS = ["BLD-0049", "BLD-0058", "BLD-0059", "CC-0009", "CC-0010", "CC-0012",
         "CC-0019", "CNF-0077", "CNF-0132", "CNF-0133", "CNF-0136", "CNF-0147"]

per_unit = {}
for uid in UNITS:
    u = bat["units"][uid]
    primary = []
    for f in u["fails"]:
        if f.startswith("S4"):
            primary.append({"check": "output_schema", "detail": f})
        elif f.startswith("S5"):
            primary.append({"check": "reviewer_closure_genuine", "detail": f})
        elif f.startswith("S3"):
            primary.append({"check": "manifest_sha", "detail": f})
        elif f.startswith("S2"):
            primary.append({"check": "artifact_predicate", "detail": f})
        elif f.startswith("P "):
            primary.append({"check": "probes_exit0", "detail": f})
    # schema instrument counts + sibling control
    sch = {}
    for s, sl in u["schema"].items():
        sch[s] = {"canonical_violations": sl["n1"], "direct_jsonschema_violations": sl["n2"],
                  "same_schema_siblings": sl["siblings_total"], "clean_siblings": sl["siblings_clean"]}
    # probes summary
    probes = {name: {"rc": p["rc"], "marker": p["marker"][:80]} for name, p in u["probes"].items()}
    per_unit[uid] = {
        "verdict": u["verdict"],
        "failing_checks": primary,
        "artifact_state": u["artifact"].get("state"),
        "manifest_rows": u["manifest"].get("n_rows"),
        "manifest_sha_all_match": not any(x.startswith("S3") for x in u["fails"]),
        "schema": sch,
        "receipt_admission": u.get("receipt_admission"),
        "reviewer_block": (u.get("reviewer_block") or {}).get("reviewer_id"),
        "reviewer_block_genuine": not any(f.startswith("S5") for f in u["fails"]),
        "probes": probes,
    }

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
verdicts = {
    "reviewer": "review:w4s6-r2 (wave 4 shard 6 independent reviewer, re-review 2026-10-26)",
    "wave": 4, "shard": 6,
    "program": "estate P2 fail-closed program",
    "repo": "C:/Users/Prekzursil/p2-g1",
    "units": UNITS,
    "verdict_rule": "ALL checks hold -> PASS closure; ANY fails -> FAIL with the precise failing check, receipt unchanged. A dishonest PASS poisons a fail-closed program.",
    "result": {"PASS": sum(1 for v in per_unit.values() if v["verdict"] == "PASS"),
               "FAIL": sum(1 for v in per_unit.values() if v["verdict"] == "FAIL")},
    "prior_run_reconciliation": {
        "prior_run": "_reviewer-w4-shard6 (2026-10-26T06:58Z, 12 FAIL, schema-primary)",
        "artifact_changed_since_prior": False,
        "this_run_agrees": "12/12 FAIL reproduced independently (fresh battery, own instruments)",
        "correction_to_prior": ("CNF-0136 S3 manifest-bytes flag from the prior run does NOT reproduce: "
                                "the manifest bytes convention is LF-normalized length (declared 11631 == "
                                "LF-normalized 11631; raw 11950) and the sha256 matches under the "
                                "CRLF->LF normalization required by the contract. Manifest is CLEAN; "
                                "CNF-0136 still fails on output_schema (65) + stamped reviewer."),
        "probe_marker_note": ("CNF-0077/CNF-0147 probes emit JSON with all_ok:true and exit 0 but no "
                              "terminal SUCCESS: marker; exit 0 is the contract requirement, so no "
                              "probe failure is recorded."),
    },
    "schema_closure_premise": ("All 9 catalog schema files mtime 2026-10-24T05:50:05Z, predating every "
                               "closure these receipts rely on; the wave-2 shard-7 'schema tightened "
                               "after closure' adjudication premise is refuted for this shard. Existing "
                               "shard7-w2 PASS closures are NOT confirmed by this reviewer."),
    "per_unit": per_unit,
    "receipt_actions": "receipt-unchanged (fail contract): no receipt, manifest, artifact or closure written by this reviewer",
    "evidence": {
        "battery": "_reviewer-w4-shard6-r2/battery_out.json",
        "probe_logs": "_reviewer-w4-shard6-r2/logs/",
        "census": "_reviewer-w4-shard6-r2/census_out.json",
    },
}
(OUT / "verdicts.json").write_text(json.dumps(verdicts, indent=1), encoding="utf-8")

ret = {
    "reviewer_id": "w4-shard6-independent-reviewer-r2-20261026",
    "wave": 4, "shard": 6,
    "program": "estate P2 fail-closed program",
    "repo": "C:/Users/Prekzursil/p2-g1",
    "reviewed_at": now,
    "verdict_summary": {"PASS": 0, "FAIL": 12, "confirmed_existing_pass": 0, "closures_written": []},
    "units": {uid: {"verdict": v["verdict"],
                    "failing_check": "; ".join(fc["check"] for fc in v["failing_checks"]) or "none",
                    "primary": v["failing_checks"][0]["detail"][:220] if v["failing_checks"] else ""}
              for uid, v in per_unit.items()},
    "checks_holding_all_12": [
        "S1 catalog entries present",
        "S2 artifacts exist/non-empty/parses/not-self-blocked, sentinels present (state=SUCCESS on all 12)",
        "S3 manifest rows sha256+bytes match live under CRLF->LF for all 12 (incl. CNF-0136 under LF-normalized bytes convention)",
        "P 24/24 probes re-executed live by this reviewer, all exit 0",
    ],
    "failing_check": ("S4 output_schema: canonical schema_resolver.validate_artifact fails for 12/12 "
                      "(violation counts: BLD-0049=1, BLD-0058=32, BLD-0059=42, CC-0009=1, CC-0010=34, "
                      "CC-0012=19, CC-0019=4, CNF-0077=3, CNF-0132=47, CNF-0133=39, CNF-0136=65, "
                      "CNF-0147=5); cross-confirmed by direct jsonschema (second instrument) and "
                      "receipt_validate admission REJECT 12/12 (third signal); same-schema sibling "
                      "census shows every schema satisfiable (230 clean receipt.schema siblings etc.) "
                      "so these are per-artifact defects, not schema drift. "
                      "S5 (5 units CC-0009/CC-0012/CNF-0077/CNF-0132/CNF-0136/CNF-0147): reviewer blocks "
                      "are builder-stamped probe-derived identities (e.g. CC-0009-probe2-reviewer-phantom), "
                      "not genuine independent closures - receipt_core forbids state=SUCCESS on those."),
    "receipt_actions": "receipt-unchanged (fail contract)",
    "fleet_position": {
        "note": "program-wide staged funnel, strict DELIVERED contract",
        "total_units": cens["total_units"],
        "stage_funnel": cens["stage_funnel"],
        "full_green": cens["full_green"],
    },
    "evidence": {
        "battery": "_reviewer-w4-shard6-r2/battery_out.json",
        "census": "_reviewer-w4-shard6-r2/census_out.json",
        "probe_logs": "_reviewer-w4-shard6-r2/logs/",
    },
}
(OUT / "REVIEW-RETURN.json").write_text(json.dumps(ret, indent=1), encoding="utf-8")

# post-battery integrity: the 12 artifacts must be byte-identical to what the battery hashed
bad = []
for uid in UNITS:
    u = bat["units"][uid]
    p = REPO / u["output_path"]
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    sha = hashlib.sha256(raw).hexdigest()
    rows = u["manifest"]["rows"]
    art_row = next((r for r in rows if r["path"].endswith(u["output_path"].split("/")[-1])), None)
    if art_row and art_row.get("live_sha") and sha[:12] != art_row["live_sha"]:
        bad.append(uid)
print("post-battery integrity:", "CLEAN (12/12 unchanged)" if not bad else "CHANGED: " + ",".join(bad))
print("verdicts.json + REVIEW-RETURN.json written")
print("PASS:", verdicts["result"]["PASS"], "FAIL:", verdicts["result"]["FAIL"])
