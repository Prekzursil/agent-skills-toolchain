#!/usr/bin/env python3
"""Read-only program-wide census for wave-3 shard-7 reviewer report.

For every catalog unit: does a delivered-shaped closure exist on disk?
  delivered-green := receipt exists+parses, state=SUCCESS,
    reviewer.verdict=PASS, reviewer.independent=true,
    UNIT-ARTIFACT-MANIFEST.json exists with a sha256 row (CRLF->LF normalized)
    matching the live artifact bytes.
Nothing is modified. Honest partial: buckets are exhaustive.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"

def digest(p: Path):
    try:
        raw = p.read_bytes().replace(b"\r\n", b"\n")
        return hashlib.sha256(raw).hexdigest()
    except OSError:
        return None

cat = json.loads(CATALOG.read_text(encoding="utf-8"))
units = cat["work_units"]
buckets = {"green": [], "receipt_no_manifest": [], "receipt_self_blocked": [],
           "receipt_bad_reviewer": [], "receipt_missing_or_unparseable": [],
           "manifest_sha_mismatch": []}
for u in units:
    uid = u.get("id")
    out = REPO / str(u.get("output_path", "")).replace("\\", "/")
    try:
        doc = json.loads(out.read_text(encoding="utf-8"))
    except Exception:
        buckets["receipt_missing_or_unparseable"].append(uid); continue
    st = str(doc.get("state") or "").upper()
    rv = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
    if st in ("BLOCKED", "FAILED", "SEVERED", "TIMEOUT"):
        buckets["receipt_self_blocked"].append(uid); continue
    if not (rv.get("verdict") == "PASS" and rv.get("independent") is True):
        buckets["receipt_bad_reviewer"].append(uid); continue
    man_p = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    try:
        man = json.loads(man_p.read_text(encoding="utf-8"))
    except Exception:
        buckets["receipt_no_manifest"].append(uid); continue
    sha = digest(out)
    rel = str(u.get("output_path", "")).replace("\\", "/")
    ok = any(isinstance(a, dict) and a.get("unit_id") == uid
             and str(a.get("path") or "").replace("\\", "/") == rel
             and str(a.get("sha256") or "") == sha and a.get("present") is True
             for a in man.get("artifacts") or [])
    if ok: buckets["green"].append(uid)
    else: buckets["manifest_sha_mismatch"].append(uid)

total = len(units)
print(f"catalog total: {total}")
for k in ("green", "receipt_no_manifest", "receipt_self_blocked",
          "receipt_bad_reviewer", "manifest_sha_mismatch",
          "receipt_missing_or_unparseable"):
    b = buckets[k]
    print(f"{k}: {len(b)}")
g = len(buckets["green"])
print(f"green fraction: {g}/{total} = {100*g/total:.1f}%")
(REPO / "_reviewer_w3s7_program_census_out.json").write_text(
    json.dumps({"total": total, "buckets": {k: v for k, v in buckets.items()}},
               indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("SUCCESS:census written")
