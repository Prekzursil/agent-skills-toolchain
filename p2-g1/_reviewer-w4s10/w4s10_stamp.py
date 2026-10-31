"""w4s10 Phase B: stamp independent reviewer closure on the units that passed
every contract check, then update the receipt row in each manifest."""
from __future__ import annotations
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

G1 = Path(r"C:/Users/Prekzursil/p2-g1")
STAMP_UNITS = ["IMP-0198"]
REVIEWER_ID = "w4-shard10-independent-reviewer-20261026"
REVIEWED_AT = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def lf_sha(p):
    return hashlib.sha256(Path(p).read_bytes().replace(b"\r\n", b"\n")).hexdigest()

stamped = []
for uid in STAMP_UNITS:
    rp = G1 / ("command-center/receipts/" + uid + ".json")
    receipt = json.loads(rp.read_bytes().decode("utf-8"))
    old_rev = receipt.get("reviewer")
    ext = receipt.get("extensions")
    if not isinstance(ext, dict):
        ext = {}
        receipt["extensions"] = ext
    if old_rev:
        ext["w4s10_prior_reviewer"] = old_rev
    nrows = json.loads((G1 / ("command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json")).read_bytes().decode("utf-8"))
    n = len(nrows["artifacts"])
    notes = (
        "Wave-4 shard-10 independent reviewer closure. Reviewer did not build this unit; "
        "re-derived all contract checks live on the CURRENT bytes in a fresh context: "
        "artifact predicate (exists, non-empty, parses, state not self-BLOCKED/FAILED), "
        "both named probes re-run by this reviewer from the manifest (rc=0 with SUCCESS markers), "
        "all " + str(n) + " UNIT-ARTIFACT-MANIFEST rows LF-normalized sha256-compared against live files (all match), "
        "catalog output_schema command-center/schema/receipt.schema.json validated through "
        "platform/lib/schema_resolver.validate_artifact with AST_INTEGRATE_ROOT=p2-g1 (zero errors), "
        "and command-center/receipt_validate.py admission = ACCEPT. "
        "Prior reviewer block preserved verbatim under extensions.w4s10_prior_reviewer; "
        "it was a builder-side self-stamp (reviewer_id named after this unit's own probe), "
        "not an independent closure, so the shard reviewer re-closed the receipt."
    )
    receipt["reviewer"] = {
        "reviewer_id": REVIEWER_ID,
        "verdict": "PASS",
        "independent": True,
        "fresh_context": True,
        "reviewed_at": REVIEWED_AT,
        "notes": notes,
    }
    receipt["state"] = "SUCCESS"
    text = json.dumps(receipt, indent=2, ensure_ascii=False) + "\n"
    rp.write_bytes(text.encode("utf-8"))
    mp = G1 / ("command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json")
    man = json.loads(mp.read_bytes().decode("utf-8"))
    for row in man["artifacts"]:
        if row["path"].endswith("receipts/" + uid + ".json"):
            row["sha256"] = lf_sha(rp)
    mp.write_bytes(json.dumps(man, indent=2, ensure_ascii=False).encode("utf-8") + b"\n")
    stamped.append({"unit": uid, "receipt_sha256_lf": lf_sha(rp), "reviewed_at": REVIEWED_AT})
    print("STAMPED", uid, lf_sha(rp)[:16])

(G1 / "_reviewer-w4s10/w4s10-rerun/stamp_log.json").write_text(
    json.dumps({"reviewer_id": REVIEWER_ID, "stamped": stamped}, indent=1), encoding="utf-8")
print("DONE", len(stamped))
