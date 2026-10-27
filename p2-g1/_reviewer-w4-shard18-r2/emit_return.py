"""Emit REVIEW-RETURN.json for wave 4 shard 18 (reviewer r2 run).

Reads _reviewer-w4-shard18-r2/battery-results.json (evidence produced by THIS
run: probes re-run, shas recomputed, schema validated both interpretations) and
writes the typed verdict document. Receipts are NOT modified here or anywhere
in this review: every unit failed at least one check, so per the unit contract
every verdict is FAIL with the receipt unchanged.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
UNITS = [
    "TST-0092", "TST-0094", "TST-0100", "TST-0109", "TST-0113", "TST-0116",
    "TST-0124", "TST-0129", "TST-0130", "TST-0136", "TST-0137", "TST-0138",
]

bat = json.loads((HERE / "battery-results.json").read_text(encoding="utf-8"))
cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
cmap = {u["id"]: u for u in cat["work_units"] if isinstance(u, dict) and u.get("id")}

# Additional reviewer-verified facts recomputed this run (independent of battery):
#   TST-0129: primary artifact row path absent on disk; supporting row sha mismatch
#   TST-0130: receipt's own primary row anchors bytes=54880/sha=5c62ea3f... but
#             live file is 50020 bytes / sha 234a633e... (receipt edited after its
#             own anchoring) - reviewer-recomputed both raw and LF-normalized.
EXTRA = {
    "TST-0129": [
        "gate: primary artifact row points at command-center/p2-wave/cloud-ok-2026-08-17/tree/... which is ABSENT on this worktree (reviewer-verified)",
        "gate: supporting row tools/lib/net-allowlist.mjs live LF sha f597bf2796a2 disagrees with declared 10e36b13ae43",
    ],
    "TST-0130": [
        "coherence: receipt INTERNALLY INCONSISTENT - its own primary artifacts row declares bytes=54880/sha256=5c62ea3f... but the live receipt file is 50020 bytes / sha256 234a633e... (reviewer recomputed raw and LF-normalized)",
    ],
}

verdicts = {}
for uid in UNITS:
    r = bat[uid]
    c = r["checks"]
    d = r["detail"]["D"]
    failing = []
    if not c["A_artifact"]:
        a = r["detail"]["A"]
        failing.append(
            "A: receipt is self-declared %s (failure.classification=%s) - not delivered by definition"
            % (a["state"], json.dumps(json.loads((REPO / "command-center/receipts" / (uid + ".json")).read_text(encoding="utf-8")).get("failure", {}).get("classification")))
        )
        failing.extend(EXTRA.get(uid, []))
    if not c["D_schema"]:
        v = d["interpretations"].get("verbatim", [])
        cn = d["interpretations"].get("canonical", [])
        failing.append(
            "D: catalog output_schema %r FAILS under BOTH interpretations - verbatim: %d error(s), program-canonical: %d error(s); representative: %s"
            % (cmap[uid].get("output_schema"), len(v), len(cn), (cn or v)[0][:140])
        )
        for e in (cn or v)[:3]:
            failing.append("    schema-error: " + e[:160])
    verdicts[uid] = {
        "verdict": "FAIL",
        "state_on_disk": r["detail"]["A"]["state"],
        "receipt_unchanged": True,
        "checks": {
            "A_artifact_exists_nonempty_parses_notblocked": c["A_artifact"],
            "B_probes_rerun_exit0": "%d/%d exit 0" % (
                sum(1 for p in r["detail"]["B"] if p.get("exit_code") == 0),
                len(r["detail"]["B"]),
            ),
            "C_manifest_sha_match_LF": c["C_manifest_sha"],
            "D_output_schema_valid": c["D_schema"],
            "E_receipt_core_invariant": c["E_receipt_core_invariant"],
        },
        "failing_checks": failing,
        "prior_stamp": "receipt carries reviewer.verdict=PASS/independent=true stamped under the pre-schema-tightening bar; this re-verification does NOT confirm it (checks above fail), stamp left untouched per fail-closed contract",
    }

ret = {
    "reviewer_wave": "w4",
    "shard": 18,
    "review_run": "r2 (fresh independent re-verification after the 0-token reviewer-agent failure; no input taken from the earlier _reviewer-w4-shard18 run's conclusions)",
    "reviewer_model": "claude-opus-5-5 (independent reviewer, did not build any shard18-w4 unit)",
    "review_utc": "2026-10-26",
    "method": [
        "unit list cross-checked: _shard18-w4/precheck.py (builder) == catalog entries == probes/<id>/ dirs; 12 units",
        "A: artifact exists/non-empty/parses/state-not-self-blocked/sentinel via catalog output_path - battery.py this run",
        "B: all %d probe commands re-run by THIS reviewer, full inherited env, PYTHONDONTWRITEBYTECODE=1 python -B, cwd=repo (PROBE-CMDS.json verbatim; probe1*/probe2* enumerated for the 7 probe dirs without PROBE-CMDS.json): %d/%d exit 0"
        % (
            sum(len(r["detail"]["B"]) for r in bat.values()),
            sum(1 for r in bat.values() for p in r["detail"]["B"] if p.get("exit_code") == 0),
            sum(len(r["detail"]["B"]) for r in bat.values()),
        ),
        "C: sha256 recomputed CRLF->LF-normalized vs UNIT-ARTIFACT-MANIFEST.json row (unit_id+path+present=true): 12/12 match",
        "D: output_schema validated under TWO interpretations - (D1 verbatim: catalog shim document + fragment pointer) and (D2 program-canonical: parse_schema_ref -> physical control plane platform/schema/receipt.schema.json + fragment); the 10 SUCCESS receipts fail under BOTH",
        "detector controls: TST-0129/TST-0130 (BLOCKED) validate schema-clean and TST-0187 (legitimate SUCCESS+PASS closure elsewhere in the program) validates clean against ITS catalog output_schema - the instrument fires on the 10 and stays silent on valid receipts (both-states proven)",
        "E: receipt_core invariant (state=SUCCESS => reviewer PASS + independent=true): holds textually on all 12 (prior stamps); material validity assessed above",
        "receipts: UNTOUCHED - any-fails => verdict FAIL with receipt unchanged per unit contract",
    ],
    "verdicts": verdicts,
    "program_context": {
        "note": "owner asked how far the program is from full 2007 green; full sweep in census-2007.json this dir",
        "catalog_units": 2007,
        "receipts_present": 2007,
        "success": 1990,
        "success_with_independent_pass": 1965,
        "success_with_independent_pass_AND_schema_clean": 1180,
        "blocked": 10,
        "other_nonterminal": 7,
    },
}

(HERE / "REVIEW-RETURN.json").write_text(json.dumps(ret, indent=1), encoding="utf-8")
print("wrote REVIEW-RETURN.json:", len(verdicts), "verdicts, all FAIL")
for uid, v in verdicts.items():
    print(uid, v["state_on_disk"], "|", v["failing_checks"][0][:110])
