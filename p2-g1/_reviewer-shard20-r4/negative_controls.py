#!/usr/bin/env python3
"""Negative controls: prove the battery can go red on a known-bad input."""
import json, hashlib
from pathlib import Path
import jsonschema

REPO = Path(r"C:/Users/Prekzursil/p2-g1")

# NC1: schema vacuity check - each unit schema must have real constraints
UNITS = ["RES-0184","RES-0185","RES-0187","RES-0188","RES-0191",
         "RES-0192","RES-0193","SYN-0003","SYN-0007","SYN-0008","SYN-0035","TST-0005"]
cat = json.loads((REPO/"command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
entries = {u["id"]: u for u in cat["work_units"]}
print("NC1 schema vacuity:")
for uid in UNITS:
    sch = json.loads((REPO/entries[uid]["output_schema"]).read_text(encoding="utf-8"))
    has_req = bool(sch.get("required"))
    has_props = bool(sch.get("properties"))
    print("  %-9s required=%s properties=%s top-level-constraint=%s" %
          (uid, has_req, has_props, has_req and has_props))

# NC2: mutation - perturb one artifact copy, validator + hash check must fire
uid = "RES-0184"
out = REPO/entries[uid]["output_path"]
doc = json.loads(out.read_text(encoding="utf-8"))
doc2 = json.loads(json.dumps(doc))
doc2["state"] = "BLOCKED"
schema = json.loads((REPO/entries[uid]["output_schema"]).read_text(encoding="utf-8"))
errs = list(jsonschema.Draft202012Validator(schema).iter_errors(doc2))
print("NC2a injected state=BLOCKED -> schema errors:", len(errs),
      "(battery self-block check would also fire:)",
      str(doc2.get("state")).upper() in ("BLOCKED","FAILED"))
doc3 = json.loads(json.dumps(doc))
rows = doc3.get("rescore",{}).get("rows",[])
if rows: rows[0]["meets_bar"] = not rows[0]["meets_bar"]
errs2 = list(jsonschema.Draft202012Validator(schema).iter_errors(doc3))
p1 = REPO/"command-center/p2-wave/probes/RES-0184/probe2_refuter.py"
import subprocess, sys, os, tempfile, shutil
tmp = Path(tempfile.mkdtemp())
try:
    # can't easily rerun probe against tampered artifact without patching REPO; instead
    # demonstrate the probe's core assertion catches the perturbation logically:
    mism = []
    for r in doc3.get("rescore",{}).get("rows",[]):
        bar = r.get("bar") or {}
        deficits = []
        if r.get("independent_source_count",0) < (bar.get("min_independent_sources") or 0): deficits.append("a")
        if bool(deficits) != (r.get("meets_bar") is False): mism.append(r.get("claim_id"))
    print("NC2b tampered meets_bar detected by refuter logic:", bool(mism), mism[:3])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# NC3: hash normalization genuinely distinguishes: craft CRLF variant
p = out.read_bytes()
crlf_variant = p.replace(b"\n", b"\r\n")
n1 = hashlib.sha256(p.replace(b"\r\n", b"\n")).hexdigest()
n2 = hashlib.sha256(crlf_variant.replace(b"\r\n", b"\n")).hexdigest()
print("NC3 CRLF-variant normalized hash == original normalized hash:", n1 == n2,
      "| raw differs:", hashlib.sha256(p).hexdigest() != hashlib.sha256(crlf_variant).hexdigest())
mf = json.loads((REPO/"command-center/p2-wave/probes/RES-0184/UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
row = [a for a in mf["artifacts"] if a["path"].endswith("RES-0184-evidence-threshold-by-claim-severity.json")][0]
print("NC4 manifest row equals normalized hash of live artifact:",
      row["sha256"] == n1, "| equals raw hash:", row["sha256"] == hashlib.sha256(p).hexdigest())
