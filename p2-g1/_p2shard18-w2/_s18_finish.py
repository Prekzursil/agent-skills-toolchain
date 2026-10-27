#!/usr/bin/env python3
"""Shard-18 finisher: re-anchor RES-0112 citations, pass-2 refresh RES-0137,
write per-unit manifests + SUBAGENT-RETURNs + BLOCKED (reviewer-absent) receipts."""
from __future__ import annotations
import hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

WS = Path("C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(WS / "command-center/p2-wave"))
import _p2lib as P  # noqa: E402
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
CAT = json.load(open(WS / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
BYID = {u["id"]: u for u in CAT["work_units"]}
IDS = ["RES-0112","RES-0114","RES-0128","RES-0131","RES-0132","RES-0137",
       "RES-0140","RES-0141","RES-0144","RES-0148","RES-0149","RES-0150"]

def art_path(uid):
    return WS.joinpath(*BYID[uid]["output_path"].split("/"))

def norm_sha(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

def run_probe(uid, script):
    cmd = [sys.executable, "-B", str(WS / "command-center/p2-wave/probes" / uid / script)]
    r = subprocess.run(cmd, cwd=str(WS), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()

# ---------- RES-0112: re-anchor gate citations to THIS tree's line numbers ----------
a = art_path("RES-0112")
doc = json.loads(a.read_text(encoding="utf-8"))
measure_rel = "command-center/p2-wave/_measure_one_delivered.py"
mlines = (WS / measure_rel).read_text(encoding="utf-8").splitlines()
def find_line(snippet):
    hits = [i + 1 for i, l in enumerate(mlines) if snippet in l]
    assert hits, snippet
    return hits[0]
patched = 0
for row in doc.get("property_gap_table", []):
    for c in row.get("gate_citations", []):
        if str(c.get("path", "")).endswith("_measure_one_delivered.py"):
            new = find_line(c["snippet"])
            if isinstance(c.get("end_line"), int):
                span = c["end_line"] - c["line"]
                c["end_line"] = new + span
            c["line"], c["prior_line"] = new, c["line"]
            patched += 1
doc.setdefault("extensions", {})["wave2_resume"] = {
    "at": NOW, "by": "builder shard 18 wave 2",
    "note": ("gate citations re-anchored to this tree's _measure_one_delivered.py "
             "(canonical copy carries repair comments that shift line numbers); "
             "snippets unchanged, %d citations re-lined" % patched),
}
rev = doc.get("reviewer") or {}
extra = {k: rev.pop(k) for k in ("default_when_insufficient",
                                 "surviving_claims_strongest_caveat") if k in rev}
if extra:
    doc["extensions"]["reviewer_extra_keys_preserved"] = extra
errs = P.validate(doc, BYID["RES-0112"]["output_schema"])
assert not errs, errs[:6]
a.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print("RES-0112: re-anchored", patched, "citations; artifact", a.stat().st_size, "B")
