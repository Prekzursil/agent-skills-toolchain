#!/usr/bin/env python3
"""Shard17 w4 resume: static disk census over all catalog units.

Replicates _measure_one_delivered disk checks WITHOUT probe re-run:
  receipt exists + non-empty + parses + state not in NOT_DELIVERING + sentinel present
  + SUBAGENT-RETURN parses + status not NOT_DELIVERING
  + probes/<id>/UNIT-ARTIFACT-MANIFEST.json row (unit_id, path, sha256 CRLF-normalized, present)
Probes were re-run live for shard 17's own 12 units.
"""
import hashlib, json, re, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CAT = json.loads((REPO/"command-center"/"WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
NOT_DELIVERING = {"BLOCKED","FAILED","SEVERED","TIMEOUT"}
UID_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")

buckets = {"delivered-static": [], "self-declared-blocked": [], "self-declared-failed": [],
           "receipt-absent": [], "receipt-unparseable": [], "sentinel-absent": [],
           "return-problem": [], "manifest-mismatch": [], "manifest-absent": [], "probe-dir-absent": []}
for u in CAT["work_units"]:
    uid = u.get("id","")
    if not UID_RE.match(uid): continue
    probe_dir = REPO/"command-center"/"p2-wave"/"probes"/uid
    out = REPO / str(u.get("output_path") or "")
    if not probe_dir.is_dir(): buckets["probe-dir-absent"].append(uid); continue
    if not out.is_file() or out.stat().st_size <= 0:
        buckets["receipt-absent"].append(uid); continue
    try:
        text = out.read_text(encoding="utf-8"); doc = json.loads(text)
    except Exception:
        buckets["receipt-unparseable"].append(uid); continue
    st = str(doc.get("state") or "").upper() if isinstance(doc, dict) else ""
    if st in NOT_DELIVERING:
        buckets["self-declared-blocked" if st=="BLOCKED" else "self-declared-failed"].append(uid); continue
    sentinel = str(u.get("completion_sentinel") or "")
    if sentinel and sentinel not in text:
        buckets["sentinel-absent"].append(uid); continue
    ret_p = probe_dir/"SUBAGENT-RETURN.json"; man_p = probe_dir/"UNIT-ARTIFACT-MANIFEST.json"
    if not ret_p.is_file() or not man_p.is_file():
        buckets["manifest-absent"].append(uid); continue
    try:
        ret = json.loads(ret_p.read_text(encoding="utf-8"))
        man = json.loads(man_p.read_text(encoding="utf-8"))
    except Exception:
        buckets["return-problem"].append(uid); continue
    st_ret = str(ret.get("status") or ret.get("state") or "").upper()
    if st_ret in NOT_DELIVERING:
        buckets["return-problem"].append(uid); continue
    out_rel = str(u.get("output_path")).replace("\\","/")
    rows = [a for a in (man.get("artifacts") or []) if isinstance(a,dict) and a.get("unit_id")==uid
            and str(a.get("path") or "").replace("\\","/")==out_rel and a.get("present") is True]
    live = hashlib.sha256(out.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    if not any(str(a.get("sha256") or "")==live for a in rows):
        buckets["manifest-mismatch"].append(uid); continue
    buckets["delivered-static"].append(uid)

total = sum(len(v) for v in buckets.values())
print(json.dumps({k: len(v) for k,v in buckets.items()}, indent=1))
print("TOTAL classified:", total)
out = REPO/"command-center"/"_builder_shard17_w4_census_out.json"
out.write_text(json.dumps({"buckets": {k: v for k,v in buckets.items()}, "total": total}, indent=1), encoding="utf-8")
print("wrote", out)
