#!/usr/bin/env python3
"""Independent reviewer wave2 shard11: mechanical pre-checks."""
import hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path.home() / "p2-g1"
UNITS = ["IMP-0095","IMP-0096","IMP-0102","IMP-0107","IMP-0122","IMP-0133",
         "IMP-0138","IMP-0146","IMP-0151","IMP-0153","IMP-0160","IMP-0161"]

def lf_hash(p: Path) -> tuple[str, int, bool]:
    raw = p.read_bytes()
    crlf = b"\r\n" in raw
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(), len(raw), crlf

cat = json.load(open(ROOT/"command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
wu = {u["id"]: u for u in cat["work_units"]}

import jsonschema
schema = json.load(open(ROOT/"command-center/schema/receipt.schema.json", encoding="utf-8"))

report = {}
for u in UNITS:
    e = wu[u]
    rp = ROOT / e["output_path"]
    row = {"catalog_out": e["output_path"]}
    if not rp.exists():
        row["artifact"] = "MISSING"; report[u] = row; continue
    h, n, crlf = lf_hash(rp)
    row["artifact_bytes"] = n; row["crlf"] = crlf
    try:
        r = json.load(open(rp, encoding="utf-8"))
        row["parses"] = True
    except Exception as ex:
        row["parses"] = f"ERROR {ex}"; report[u] = row; continue
    row["state"] = r.get("state")
    row["failure"] = (r.get("failure") or {}).get("classification")
    row["failure_reason_head"] = str((r.get("failure") or {}).get("reason"))[:110]
    row["min_bytes"] = r.get("min_bytes_threshold")
    row["n_evidence"] = len(r.get("evidence", []))
    row["n_tests"] = len(r.get("tests", []))
    test_results = [t.get("result") for t in r.get("tests", [])]
    row["test_results"] = test_results
    row["n_negctl"] = len(r.get("negative_controls", []))
    row["negctl_flags"] = [(c.get("fired_on_bad_state"), c.get("silent_on_good_state")) for c in r.get("negative_controls", [])]
    row["n_downstream"] = len(r.get("downstream_consumers", []))
    row["downstream_flags"] = [(c.get("executed"), c.get("read_ok")) for c in r.get("downstream_consumers", [])]
    row["residual_unknowns_n"] = len(r.get("residual_unknowns", []))
    row["sentinel"] = r.get("sentinel")
    row["manifest_registration"] = r.get("manifest_registration")
    mf = ROOT / "command-center/p2-wave/probes" / u / "UNIT-ARTIFACT-MANIFEST.json"
    m = json.load(open(mf, encoding="utf-8"))
    arts = m.get("artifacts", [])
    row["manifest_rows"] = []
    for a in arts:
        ap = ROOT / a["path"]
        ah, an, acrlf = lf_hash(ap)
        row["manifest_rows"].append({
            "path": a["path"], "manifest_sha": a.get("sha256"),
            "live_lf_sha": ah, "match_lf": ah == a.get("sha256"),
            "bytes_manifest": a.get("bytes"), "bytes_live": an,
        })
    try:
        jsonschema.validate(r, schema)
        row["schema_now"] = "VALID"
    except jsonschema.ValidationError as ex:
        row["schema_now"] = f"INVALID: {ex.message[:220]}"
    report[u] = row

print(json.dumps(report, indent=1))
