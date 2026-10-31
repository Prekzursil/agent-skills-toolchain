#!/usr/bin/env python3
"""Independent reviewer verification for shard 5 (12 units).
Checks per unit: manifest artifact rows (sha256 CRLF-normalized + bytes + present),
primary artifact == catalog output_path."""
import hashlib, json, os, sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = ['CNF-0173','CNF-0177','CNF-0178','CNF-0180','CNF-0188','CNL-0076',
         'IMP-0003','IMP-0013','IMP-0014','IMP-0018','IMP-0020','IMP-0022']

def norm_sha(p: Path) -> tuple[str, int]:
    raw = p.read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(raw)

catalog = json.loads((REPO/"command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
wu = {u["id"]: u for u in catalog["work_units"]}

failures = []
rows = []
for uid in UNITS:
    mpath = REPO/f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
    if not mpath.exists():
        failures.append(f"{uid}: manifest missing at {mpath}")
        continue
    man = json.loads(mpath.read_text(encoding="utf-8"))
    if man.get("unit_id") != uid:
        failures.append(f"{uid}: manifest unit_id={man.get('unit_id')}")
    expected, present = man.get("expected"), man.get("present")
    arts = man.get("artifacts") or []
    if present != len(arts):
        failures.append(f"{uid}: present={present} != len(artifacts)={len(arts)}")
    if expected != len(arts):
        failures.append(f"{uid}: expected={expected} != len(artifacts)={len(arts)}")
    out_path = wu[uid]["output_path"].replace("/", "\\")
    primary_rows = [a for a in arts if a.get("role") == "primary"]
    if len(primary_rows) != 1:
        failures.append(f"{uid}: {len(primary_rows)} primary rows")
    for a in arts:
        ap = REPO/a["path"]
        if not ap.exists():
            failures.append(f"{uid}: artifact MISSING {a['path']}")
            continue
        sha, nb = norm_sha(ap)
        ok_sha = sha == a.get("sha256")
        ok_bytes = nb == a.get("bytes")
        if not ok_sha:
            failures.append(f"{uid}: SHA MISMATCH {a['path']} manifest={a.get('sha256')[:12]} live={sha[:12]}")
        if not ok_bytes:
            failures.append(f"{uid}: BYTES MISMATCH {a['path']} manifest={a.get('bytes')} live={nb}")
        if not a.get("present"):
            failures.append(f"{uid}: manifest row present=false {a['path']}")
    # primary artifact must be the catalog output_path
    if primary_rows and primary_rows[0]["path"] != wu[uid]["output_path"]:
        failures.append(f"{uid}: primary row path {primary_rows[0]['path']} != catalog output_path {wu[uid]['output_path']}")
    # snapshot hashes post-verification (for post-probe mutation check)
    rows.append((uid, primary_rows[0]["path"] if primary_rows else None))

print("=== MANIFEST HASH VERIFICATION ===")
if failures:
    for f in failures:
        print("FAIL:", f)
    print(f"RESULT: {len(failures)} FAILURES")
else:
    print("ALL 12 UNITS: manifest sha256(CRLF->LF) + bytes + primary==output_path ALL MATCH")
    print("RESULT: CLEAN")
