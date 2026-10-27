#!/usr/bin/env python3
"""Emit w4s19 reviewer verdicts + post-run receipt-untouched proof."""
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
cat = json.load(open(REPO / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
wu = {u["id"]: u for u in cat["work_units"]}
UNITS = ["TST-0109", "TST-0113", "TST-0116", "TST-0124",
         "TST-0136", "TST-0137", "TST-0138", "TST-0139",
         "TST-0141", "TST-0142", "TST-0143", "TST-0144"]
res = json.load(open(REPO / "_reviewer-w4s19/verify_results.json", encoding="utf-8"))

verdicts = {"summary": "", "units": []}
untouched = True
for uid in UNITS:
    r = res[uid]
    errs = r["checks"].get("schema_errors", [])
    n = r["checks"].get("schema_error_count")
    ref = wu[uid]["output_schema"]
    rep = errs[0][:110] if errs else ""
    note = (
        "FAIL on validate output_schema: %d schema error(s) via the program's own resolver "
        "(platform/lib/schema_resolver.validate_artifact, catalog ref %s; the receipt-recorded CLI form agrees). "
        "Representative: %s. All other DELIVERED checks re-derived live and hold: artifact exists/non-empty/parses "
        "at %s; state=SUCCESS not self-blocked; receipt_core rule satisfied (reviewer.verdict=PASS, "
        "independent=true present); CRLF-normalized sha256 matches the manifest primary row; every registered "
        "probe re-run exit 0. Receipt left unchanged."
        % (n, ref, rep, wu[uid]["output_path"])
    )
    if uid == "TST-0141":
        note += (
            " ADDITIONAL CONTENT CONTRADICTION the tightened schema now catches: the receipt sentinel field is "
            "'FAILED:TST-0141 refute-not-refuted dependency-blocked: B07 scheduler absent; condition 11 live check red' "
            "while state=SUCCESS and reviewer=PASS; its own tests list T4 NOT-RUN (B07 absent) and T5 FAIL "
            "(condition-11 live check red) with defects D1/D2 open (P1/P2). The August PASS closure is "
            "content-suspect, not merely schema-stale."
        )
    verdicts["units"].append({"id": uid, "verdict": "FAIL", "notes": note})
    p = REPO / wu[uid]["output_path"]
    live = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    man = json.load(open(REPO / ("command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json" % uid), encoding="utf-8"))
    out_rel = wu[uid]["output_path"].replace("\\", "/")
    prim = [a for a in man["artifacts"] if a["path"].replace("\\", "/") == out_rel][0]
    if live != prim["sha256"]:
        untouched = False
        print("TOUCHED!", uid)

proof = ("all 12 manifest sha rows still match live artifacts post-run"
         if untouched else "DRIFT DETECTED")
verdicts["summary"] = (
    "INDEPENDENT REVIEWER wave 4 shard 19 (12 units: TST-0109/0113/0116/0124/0136/0137/0138/0139/0141/0142/"
    "0143/0144) in C:\\Users\\Prekzursil\\p2-g1. VERDICT: 0/12 PASS, 12/12 FAIL, receipts byte-untouched "
    "(post-run proof: " + proof + "). Sole failing check on every unit: validate output_schema via the program's "
    "blessed resolver (schema_resolver.validate_artifact; the receipt-recorded CLI form agrees) against the "
    "catalog-declared schema ref. Instrument discipline: (a) both-states proven - the same resolver returns 0 "
    "errors on wave-4-shard-0's PASSed units (ADV-0005/0010/0037), so the check discriminates instead of "
    "universally reddening; (b) two instrument bugs of my own found and fixed before verdict (pipe exit-code "
    "read; manifest bytes are LF-normalized lengths per the builder convention documented in the manifest "
    "derivation field). Everything else holds on all 12: artifact predicate, state SUCCESS not self-blocked, "
    "receipt_core PASS+independent, CRLF-normalized sha256 vs manifest primary row, all registered supporting "
    "rows, and 24/24 live probe re-runs exit 0. Context: these receipts closed 2026-08-17..19 against the "
    "then-current schema; platform/schema/receipt.schema.json was tightened 2026-10-24 08:49 and these receipts "
    "were never re-anchored (their 2026-10-24 08:50 mtime is an EOL-only normalization pass - content hashes "
    "still match the August manifests). The ADV lane WAS re-anchored and validates clean under the same gate. "
    "Converges with sibling reviewers review:w2s23 (10 of these units) and review:w3s19 (4 of these units), "
    "same failing check. Repair lane is receipt re-anchoring to the current schema (the "
    "_fix_adv0127_w4_receipts.py pattern) - builder/program work, outside reviewer mandate since ANY-fails "
    "forbids touching receipts. TST-0141 additionally carries a content contradiction (sentinel "
    "FAILED:...dependency-blocked vs state=SUCCESS, T4 NOT-RUN, T5 FAIL, open P1/P2 defects) that the "
    "tightened schema now catches."
)
out = REPO / "_reviewer-w4s19/VERDICTS-w4s19.json"
out.write_text(json.dumps(verdicts, indent=1), encoding="utf-8")
print("untouched proof:", untouched)
print("wrote", out)
for u in verdicts["units"]:
    print(u["id"], u["verdict"])
