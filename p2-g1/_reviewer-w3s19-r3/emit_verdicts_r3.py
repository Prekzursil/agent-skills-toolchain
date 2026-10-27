#!/usr/bin/env python3
"""Emit w3s19 r3 reviewer verdicts from results_r3.json."""
import json
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
OUT = REPO / "_reviewer-w3s19-r3"

r = json.loads((OUT / "results_r3.json").read_text(encoding="utf-8"))

env_note_txt = (
    "probe transport note: TST-0100 probe2 rc=1 inside the battery is an ENVIRONMENT artifact, "
    "not an artifact defect - the reviewer harness's bash subprocess PATH lacks the PowerShell 7 dir, "
    "so shutil.which('pwsh') failed (env_note.path_has_powershell7_dir=false). Live re-run by the reviewer "
    "with the PATH restored (pwsh 7.6.9 present on this box) exited rc=0 and the pwsh rerun AGREED "
    "(decoy refused, same-shape pinned path permitted, origins carried verbatim). Probe check judged "
    "HOLDING for TST-0100; the schema failure below stands regardless."
)

schema_note = (
    "Root cause (third independent reproduction after the 06:15Z r1 and 17:53Z r2 runs, identical counts): "
    "these receipts closed 2026-08 against the then-current schema; platform/schema/receipt.schema.json was "
    "tightened 2026-10-24 08:49 (mtime verified) and the receipts were never re-anchored - their 2026-10-24 "
    "08:50 mtime is an EOL-only normalization pass and their content hashes still match the manifest rows. "
    "Repair lane is builder receipt re-anchoring to the current control plane (the _fix_adv0127_w4_receipts.py "
    "pattern), outside reviewer mandate. Only the independent reviewer may set PASS; with schema non-conformance "
    "live-reconfirmed on every unit, none of the 12 may be closed by this review."
)

verdicts = {
    "reviewer_id": "claude-opus-5-5-independent-reviewer-w3s19-r3-2026-10-26",
    "wave": "wave3",
    "shard": 19,
    "round": "r3",
    "units_total": 12,
    "positive_control": r["positive_control"],
    "env_note": r["env_note"],
    "receipts_untouched_by_reviewer": r["receipts_untouched_by_reviewer"],
    "verdicts": {},
}
for uid in r["order"]:
    x = r["results"][uid]
    v = {
        "verdict": x["verdict"],
        "primary_failing_check": "validate output_schema" if x["verdict"] == "FAIL" else None,
        "schema_errors_own_chain": x["schema_errors_own_chain"],
        "schema_errors_resolver": x["schema_errors_resolver"],
        "schema_first_own": x["schema_first_own"][:3],
        "schema_first_resolver": x["schema_first_resolver"][:3],
        "output_schema": x["output_schema"],
        "probes_all_rc0": all(p["rc"] == 0 for p in x["probe_runs"]),
        "probe_runs": x["probe_runs"],
        "manifest_rows": x["manifest_rows"],
        "manifest_primary_row_ok": x.get("primary_row_ok"),
        "receipt_state_left": x["receipt_state"],
        "notes": schema_note,
    }
    if uid == "TST-0100":
        v["notes"] = env_note_txt + " " + schema_note
    verdicts["verdicts"][uid] = v

verdicts["pass_count"] = sum(1 for v in verdicts["verdicts"].values() if v["verdict"] == "PASS")
(OUT / "VERDICTS-w3s19-r3.json").write_text(json.dumps(verdicts, indent=1), encoding="utf-8")
print("EMITTED:", str(OUT / "VERDICTS-w3s19-r3.json"))
print("PASS:", verdicts["pass_count"], "/", verdicts["units_total"])
