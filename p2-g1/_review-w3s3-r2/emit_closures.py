#!/usr/bin/env python3
"""Emit the wave-3 shard-3 independent reviewer closure record.

Reads static_results.json + probe_results_{A,B}.json (both produced by THIS
reviewer's own fresh runs) and writes closures.json: per-unit verdict +
precise failing checks. Receipts are NOT modified (all verdicts are FAIL;
contract: receipt unchanged on FAIL).
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
UNITS = ["ARC-0055", "ARC-0056", "ARC-0076", "AUD-0003", "AUD-0005", "AUD-0008",
         "AUD-0010", "AUD-0026", "AUD-0032", "AUD-0033", "AUD-0042", "AUD-0043"]

static = json.loads((HERE / "static_results.json").read_text(encoding="utf-8"))
probes = {}
for name in ("probe_results_A.json", "probe_results_B.json"):
    p = HERE / name
    if p.is_file():
        probes.update(json.loads(p.read_text(encoding="utf-8")))

closures = {
    "reviewer": "wave-3-shard-3-independent-reviewer (claude opus-5-5, fresh context)",
    "date": "2026-10-26",
    "scope": "12 units of build:w3s3 (_reviewer-w4s8/build-assignments-all-waves.json): "
             "ARC-0055, ARC-0056, ARC-0076, AUD-0003, AUD-0005, AUD-0008, AUD-0010, "
             "AUD-0026, AUD-0032, AUD-0033, AUD-0042, AUD-0043",
    "method": {
        "catalog": "command-center/WORK-UNIT-CATALOG.json entries resolved live",
        "artifact": "exists/non-empty/JSON-parse/state-not-in-{BLOCKED,FAILED,SEVERED,TIMEOUT} "
                    "at catalog output_path",
        "sentinel": "catalog completion_sentinel string must appear in artifact text",
        "manifest": "probes/<id>/UNIT-ARTIFACT-MANIFEST.json row for unit_id with "
                    "path==output_path, present=true, sha256 == live sha256 with CRLF->LF",
        "schema": "platform/lib/schema_resolver.validate_artifact (blessed registry path) "
                  "against the catalog-declared output_schema; instrument verified with "
                  "positive controls IMP-0074/IMP-0082/IMP-0146/ADV-0005 -> 0 errors",
        "probes": "T1 reviewer-direct: [sys.executable, -B, script] per named probe from "
                  "SUBAGENT-RETURN.json (2700s each); T2 program transport: "
                  "_measure_one_delivered.py (which re-checks artifact+manifest itself); "
                  "both transports must be green",
        "instrument_notes": "first C08 attempt was a reviewer-side wiring bug "
                            "(ResolvedSchema attrs) - discarded; the recorded failures are "
                            "from the corrected blessed-path instrument, corroborated by "
                            "byte-identical schema files in p2-g1 and source/ast-integrate "
                            "(artifact-class-profiles.schema.json sha256 f89a4209..., "
                            "receipt.schema.json sha256-identical) and by positive controls",
    },
    "units": {},
}

for uid in UNITS:
    s = static[uid]
    d = s["detail"]
    p = probes.get(uid, {})
    failing = []
    for k, v in s["checks"].items():
        if v is False:
            failing.append(k)
    if not p.get("T1_all_exit0", False):
        failing.append("C09_probes_T1_direct_not_all_exit0")
    if not p.get("T2_delivered", False):
        failing.append("C09_probes_T2_measure_not_delivered")
    schema_errs = d.get("schema_errors_first") or []
    verdict = "FAIL" if failing else "PASS"
    t1 = p.get("T1_direct_probes") or []
    closures["units"][uid] = {
        "verdict": verdict,
        "receipt_state": d.get("receipt_state"),
        "receipt_row_stale": d.get("receipt_row_stale", False),
        "receipt_row": d.get("receipt_row"),
        "failing_checks": failing,
        "detail": {
            "output_path": d.get("output_path"),
            "output_schema": d.get("output_schema"),
            "artifact_bytes_lf": d.get("live_bytes_lf"),
            "sha256_lf_normalized": d.get("live_sha256_lf"),
            "artifact_state": d.get("artifact_state"),
            "catalog_sentinel": d.get("catalog_sentinel"),
            "named_probe_cmds": d.get("named_probe_cmds"),
            "probe_T1": [{"cmd": x.get("cmd"), "rc": x.get("rc"),
                          "sec": x.get("sec"),
                          "marker": m} for x, m in zip(t1, p.get("T1_markers", []))],
            "probe_T2_measure_rc": (p.get("T2_measure") or {}).get("rc"),
            "probe_T2_measure_sec": (p.get("T2_measure") or {}).get("sec"),
            "n_schema_errors": d.get("n_schema_errors"),
            "schema_errors_first": schema_errs[:6],
        },
        "closure_action": (
            "receipt unchanged; unit stays open pending rebuild"
            if verdict == "FAIL"
            else "receipt updated: reviewer.verdict=PASS, independent=true, state=SUCCESS"),
    }

closures["summary"] = {
    "pass": sorted(u for u, r in closures["units"].items() if r["verdict"] == "PASS"),
    "fail": sorted(u for u, r in closures["units"].items() if r["verdict"] == "FAIL"),
    "universal_failure": "C08_schema_valid: every artifact violates its catalog-declared "
                         "artifact-class profile (architecture-review / migration-plan / "
                         "tournament-score / audit-*), which allOf receipt.schema.json "
                         "#/$defs/generic_report -> #/$defs/receipt_core and require a "
                         "receipt-shaped delivery document (schema_version, spec_anchor, "
                         "min_bytes_threshold, timestamps, retry, negative_controls, "
                         "downstream_consumers, manifest_registration, report.kind, "
                         "residual_unknowns, ...). The 12 artifacts are plain finding/"
                         "inventory documents without those blocks. Probes, manifest sha, "
                         "sentinel, and artifact presence are GREEN for all 12 on both "
                         "transports - the sole red check is output_schema validation.",
    "what_would_flip_to_pass": "re-emit each artifact as a generic_report-conformant "
                               "delivery document (report.kind=<class>, receipt_core "
                               "blocks, >=1 observation with measured/method/anchor, "
                               "control_ids) WITHOUT changing its measured claims, then "
                               "refresh the manifest row + receipt artifacts row "
                               "(ARC-0055's receipt row is additionally stale: records "
                               "19837 B / bab1ca52... vs live 20608 B / 46e591f4...), "
                               "then re-request review.",
    "receipts_modified": "NONE (all verdicts FAIL; contract: receipt unchanged)",
    "evaluated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
closures["summary"]["all_ok"] = not closures["summary"]["fail"]

out = HERE / "closures.json"
out.write_text(json.dumps(closures, indent=1, ensure_ascii=False) + "\n",
               encoding="utf-8", newline="\n")
print("wrote", out)
for uid in UNITS:
    u = closures["units"][uid]
    print(uid, u["verdict"], "|", "; ".join(u["failing_checks"])[:120])
print(("SUCCESS:" if closures["summary"]["all_ok"] else "FAILED:")
      + "reviewer-w3s3 closures emitted 12 units, pass=%d fail=%d"
      % (len(closures["summary"]["pass"]), len(closures["summary"]["fail"])))
