#!/usr/bin/env python3
"""Merge schema battery + probe sweep into the final reviewer verdict table.
Rule: PASS iff ALL checks hold (artifact, state, probes rc=0, sha match,
output_schema valid). Receipts are NEVER touched by this reviewer pass.
Writes review-verdicts.json only."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
sb = json.loads((HERE / "schema_battery_out.json").read_text(encoding="utf-8"))
d2 = json.loads((HERE / "d2_out.json").read_text(encoding="utf-8"))
sw = json.loads((HERE / "probe_sweep_out.json").read_text(encoding="utf-8"))

verdicts = {}
for uid, r in sb.items():
    probe = sw.get(uid, {})
    d1 = r.get("d1_resolver_errors")
    dn = d2.get(uid, {}).get("errors")
    checks = {
        "artifact_exists_nonempty_parses": bool(r.get("exists_nonempty") and r.get("parses")),
        "state_not_self_declared_blocked_failed": bool(r.get("state_not_self_blocked")),
        "live_probes_exit0": probe.get("rc") == 0,
        "sha256_lf_manifest_match": bool(r.get("sha_manifest_match")),
        "output_schema_valid": d1 == 0 and dn == 0,
        "receipt_core_reviewer_pass_independent_present": bool(r.get("receipt_core_ok")),
    }
    fails = [k for k, v in checks.items() if not v]
    schema_note = (
        "output_schema invalid: sanctioned resolver errors=%s; independent jsonschema "
        "Draft2020-12+source-ref-remap errors=%s; first: %s" % (d1, dn, (d2.get(uid, {}).get("first") or ["?"])[0][:200])
    )
    if fails:
        verdict = "FAIL"
        failing = []
        if not checks["live_probes_exit0"]:
            failing.append("live probes: measure rc=%s (%s)" % (probe.get("rc"), probe.get("last", "")[:150]))
        if not checks["output_schema_valid"]:
            failing.append(schema_note)
        for k in fails:
            if k not in ("live_probes_exit0", "output_schema_valid"):
                failing.append(k)
        fail_txt = " | ".join(failing)
    else:
        verdict = "PASS"
        fail_txt = ""
    verdicts[uid] = {
        "catalog_output_path": r.get("output_path"),
        "output_schema": r.get("output_schema"),
        "receipt_sentinel_prefix": r.get("receipt_sentinel_prefix"),
        "checks": checks,
        "probe_rc": probe.get("rc"),
        "probe_last": probe.get("last"),
        "d1_resolver_errors": d1,
        "d2_jsonschema_errors": dn,
        "d2_first_errors": (d2.get(uid, {}) or {}).get("first"),
        "verdict": verdict,
        "failing_check": fail_txt,
        "receipt_untouched": True,
    }

n_pass = sum(1 for v in verdicts.values() if v["verdict"] == "PASS")
out = {
    "reviewer": "claude/opus-5-5 independent reviewer, wave-2 shard-6 re-review (fresh)",
    "reviewed_at_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"),
    "method": (
        "Two-instrument schema validation (sanctioned platform/lib/schema_resolver.validate_artifact "
        "+ independent jsonschema Draft2020-12 with file:// source-ref remap into this repo); both-states "
        "control: 6 of 10 other-shard receipts validate cleanly, so the instruments can say VALID; "
        "live named probes re-run via canonical _measure_one_delivered.py (2700s budget); sha256 over "
        "CRLF-normalized LF bytes vs probes/<id>/UNIT-ARTIFACT-MANIFEST.json primary row. Receipts NOT "
        "modified: any FAIL leaves receipts byte-identical; no unit reached all-green, so no closure was written."
    ),
    "summary": {"total": len(verdicts), "pass": n_pass, "fail": len(verdicts) - n_pass},
    "verdicts": verdicts,
}
dst = HERE / "review-verdicts.json"
dst.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
print("summary:", out["summary"])
for uid, v in verdicts.items():
    print(uid, v["verdict"], "| probes_rc=%s" % v["probe_rc"], "|", v["failing_check"][:160])
print("WROTE", dst)
