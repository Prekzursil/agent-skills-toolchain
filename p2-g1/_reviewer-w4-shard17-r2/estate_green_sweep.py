#!/usr/bin/env python3
"""Estate-wide green sweep (read-only): for ALL catalog units with UID shape,
classify: receipt-absent / unparseable / self-blocked / reviewer-block-missing /
reviewer-not-independent / schema-invalid / GREEN.
GREEN = state=SUCCESS + reviewer.verdict=PASS + independent=true + schema_valid + sentinel.
Read-only. Writes estate_green_sweep.json.
"""
import hashlib, json, re, sys
from pathlib import Path
from datetime import datetime, timezone

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(REPO / "platform"))
from lib.schema_resolver import validate_artifact  # noqa: E402

UID_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")
NOT_DELIVERING = {"BLOCKED","FAILED","SEVERED","TIMEOUT"}
PROBE_DERIVED_RX = re.compile(
    r"probe\d|probe[_-]|schema-resolver|green-claim|timeout-only-mutant|coin[-_]flip", re.I)

cat = json.loads((REPO/"command-center"/"WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
buckets = {"receipt-absent": [], "unparseable": [], "self-blocked": [], "sentinel-missing": [],
           "reviewer-block-missing": [], "reviewer-not-independent": [],
           "schema-invalid": [], "GREEN": [], "non-unit-ids": []}
per_unit = {}
for u in cat["work_units"]:
    uid = u.get("id","")
    if not UID_RE.match(uid):
        buckets["non-unit-ids"].append(uid)
        continue
    out = REPO / str(u.get("output_path") or "")
    if not out.is_file() or out.stat().st_size <= 0:
        buckets["receipt-absent"].append(uid)
        continue
    try:
        text = out.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception:
        buckets["unparseable"].append(uid)
        continue
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        buckets["self-blocked"].append(uid)
        continue
    sentinel = str(u.get("completion_sentinel") or "")
    if sentinel and sentinel not in text:
        buckets["sentinel-missing"].append(uid)
        continue
    rv = doc.get("reviewer")
    if not isinstance(rv, dict) or str(rv.get("verdict") or "").upper() != "PASS" or rv.get("independent") is not True:
        buckets["reviewer-block-missing"].append(uid)
        continue
    rid = " ".join(str(rv.get(k) or "") for k in ("reviewer_id","id","role","name"))
    if PROBE_DERIVED_RX.search(rid) or "rederive" in rid.lower():
        buckets["reviewer-not-independent"].append(uid)
        per_unit[uid] = {"reviewer_id": rid[:80]}
        continue
    try:
        errs = validate_artifact(doc, u["output_schema"])
    except Exception as e:
        errs = ["resolver-error: %s" % str(e)[:100]]
    if errs:
        buckets["schema-invalid"].append(uid)
        per_unit[uid] = {"violations": len(errs)}
        continue
    buckets["GREEN"].append(uid)

n = sum(len(v) for v in buckets.values())
summary = {k: len(v) for k, v in buckets.items()}
summary["_total_classified"] = n
summary["_meta"] = {"utc": datetime.now(timezone.utc).isoformat()}
(REPO/"_reviewer-w4-shard17-r2"/"estate_green_sweep.json").write_text(
    json.dumps({"summary": {k: (v if isinstance(v, int) else v) for k, v in buckets.items()},
                "counts": summary, "detail": per_unit}, indent=1), encoding="utf-8")
for k in buckets:
    print("%-28s %d" % (k, len(buckets[k])))
print("TOTAL", n)
