import json
from pathlib import Path

p = Path("command-center/receipts/TST-0209.json")
r = json.loads(p.read_text(encoding="utf-8"))

# preserve the dead builder's reviewer claim verbatim as history
r["prior_builder_reviewer_claim"] = dict(r.get("reviewer") or {})
r["prior_builder_reviewer_claim"]["verification_status_at_handoff"] = (
    "NOT-VERIFIABLE: the probe files this entry names (probes/TST-0209/"
    "probe1_new_call_site.py, probe2_property_and_static_scan.py) and "
    "tools/lib/tests/test_sink_scrub.py did not exist on disk at the "
    "builder-death handoff, so the PASS/independent closure could not be "
    "re-run - same fabrication shape shard19-w4 documented on TST-0174."
)

r["state"] = "BLOCKED"
r["failure"] = {
    "classification": ["reviewer-absent"],
    "reason": (
        "Built-awaiting-review. The prior builder died mid-flight leaving a SUCCESS receipt whose "
        "probe-named reviewer entry had NO probe files on disk (unverifiable closure, shard19-w4 "
        "TST-0174 precedent). shard17-w4 rebuilt the real instruments - probe1_new_call_site.py "
        "(new unscrubbed call site still redacted on log/exception/telemetry; bypass mutant "
        "leaks), probe2_property_and_static_scan.py (200-shape property zero failures; AST scan "
        "clean sink-only routing; call-site-only mutant leaves a new site exposed; JS twin "
        "parity), tools/lib/tests/test_sink_scrub.py (4/4) - and re-verified every factual claim "
        "in this receipt live, exit 0. The claims HOLD; the closure itself was not an independent "
        "reviewer's. SUCCESS withheld: receipt_core forbids state=SUCCESS without "
        "reviewer.verdict=PASS + independent=true from a reviewer that can actually re-run."
    ),
}
r["reviewer"] = {
    "reviewer_id": "pending-independent-review",
    "verdict": "NOT-REVIEWED",
    "independent": False,
    "notes": (
        "An independent reviewer must re-run probe1_new_call_site.py, "
        "probe2_property_and_static_scan.py and tools/lib/tests/test_sink_scrub.py (all exit 0 "
        "this session), confirm the original receipt's claims held without modification, and "
        "acknowledge the scope limit the answer already records: estate writers not wired "
        "through this sink are NOT-CHECKED because no production logger was present."
    ),
}

# tests rows: rebuilt instruments with live reruns
r["tests"] = [
    {"id": "detector-new-unscrubbed-call-site",
     "name": "adding a NEW logging call site with an unscrubbed secret still redacts",
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0209/probe1_new_call_site.py",
     "result": "PASS", "rebuilt_by": "shard17-w4 2026-10-26"},
    {"id": "property-200-synthetic-secret-shapes-in-exceptions",
     "name": "property test over 200 synthetic secret shapes in exception messages",
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0209/probe2_property_and_static_scan.py",
     "result": "PASS", "rebuilt_by": "shard17-w4 2026-10-26"},
    {"id": "library-tests",
     "name": "sink_scrub library tests",
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/lib/tests/test_sink_scrub.py",
     "result": "PASS", "rebuilt_by": "shard17-w4 2026-10-26"},
]

r["notes"] = (r.get("notes") or "") + (
    " shard17-w4 2026-10-26 rebuild: probe dir, both probes and the library test did not exist "
    "on disk (builder died mid-flight after emitting the SUCCESS receipt with a probe-named "
    "reviewer). Instruments rebuilt from the receipt's own recorded claims against the live "
    "sinks (tools/lib/sink_scrub.py + tools/lib/security.mjs + tools/lib/observability.py); "
    "every claim verified live; original reviewer claim preserved verbatim under "
    "prior_builder_reviewer_claim; state demoted to BLOCKED reviewer-absent per the shard19-w4 "
    "TST-0174 precedent. Not owner-gated (owner_approval_required=false)."
)
if isinstance(r.get("timestamps"), dict):
    r["timestamps"]["rebuild_at"] = "2026-10-26T12:00:00Z"

p.write_text(json.dumps(r, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("receipt updated, bytes:", p.stat().st_size)
