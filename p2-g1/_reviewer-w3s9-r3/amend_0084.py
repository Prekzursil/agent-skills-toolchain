#!/usr/bin/env python3
"""Amend the IMP-0084 entry in VERDICTS-w3s9-r3.json with the concurrent-closure finding."""
import json
from pathlib import Path

P = Path(__file__).parent / "VERDICTS-w3s9-r3.json"
v = json.loads(P.read_text(encoding="utf-8"))

v["concurrent_closure_event"] = {
    "unit": "IMP-0084",
    "what": (
        "While this battery was running (receipt mtime 2026-10-26T18:31:21+02:00, between this "
        "reviewer's Phase-B parse of IMP-0084 and the post-run integrity check), a concurrent "
        "independent reviewer 'claude-opus-5-5-ind-reviewer-w3-shard10-2026-10-26' (reviewed_at "
        "2026-10-26T07:40:00Z) closed IMP-0084: rewrote the receipt reviewer block and updated the "
        "UNIT-ARTIFACT-MANIFEST.json primary row (both files mtime 18:31:21). Not this reviewer's "
        "edit; per the no-edit-under-concurrent-work rule this reviewer did NOT revert or overwrite it."
    ),
    "r3_verdict_basis": (
        "IMP-0084 verdict FAIL was rendered on the PRE-closure bytes (sha 522d8fec... matched the "
        "manifest row and r2's recorded sha at parse time)."
    ),
    "post_closure_reverification": [
        "state=SUCCESS, reviewer.verdict=PASS, independent=true (shard-10 reviewer)",
        "manifest primary row matches live post-closure bytes (registration repaired atomically)",
        "receipt.schema.json: 0 errors (both instruments)",
        "BUT tests[0] STILL records 'PYTHONDONTWRITEBYTECODE=1 python3 -B tools/marketplace/tests/"
        "test_lockfile.py -v' WITHOUT the PYTHONPATH=tools prefix -> exit 1 as recorded on the "
        "pinned runtime; with the prefix the suite passes 7/7 (substance fine, record sloppy)",
        "catalog still declares the compound output_schema whose '+' part "
        "(tools/marketplace/schema/lockfile.schema.json) has no resolver registry entry",
    ],
    "this_reviewers_position": (
        "Under the uniform as-recorded binding rule (every recorded command re-runs exit 0 + "
        "non-empty stdout), IMP-0084 still does not hold ALL checks on the current bytes either: "
        "tests[0] exits 1 as recorded and the secondary declared schema is unresolvable. The "
        "shard-10 closure evidently bound the probe check on the named probes only. Recorded here "
        "for the owner to adjudicate; no receipt was modified by this reviewer."
    ),
}

P.write_text(json.dumps(v, indent=1), encoding="utf-8")
print("amended OK")
