#!/usr/bin/env python3
"""w4-shard9 resume: full contract status for the 12 assigned units."""
import hashlib, json, subprocess, sys, os
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
UNITS = ["IMP-0202","IMP-0204","IMP-0207","IMP-0219","IMP-0224","IMP-0228",
         "IMP-0229","IMP-0230","IMP-0261","IMP-0264","IMP-0269","IMP-0270"]

def digest_file(path: Path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)

def load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"__err__": f"{type(e).__name__}: {e}"}

cat = load(CATALOG)
wu = {u.get("id"): u for u in cat.get("work_units", []) if isinstance(u, dict)}

report = {}
for uid in UNITS:
    r = {"probe_dir": False, "receipt": None, "manifest": None, "measure_rc": None, "notes": []}
    unit = wu.get(uid)
    r["catalog"] = bool(unit)
    if unit:
        r["output_path"] = unit.get("output_path")
        r["deps"] = unit.get("dependencies")
        r["owner_gate"] = unit.get("owner_approval_required")
    pdir = PROBES / uid
    r["probe_dir"] = pdir.is_dir()
    # receipt
    if unit and unit.get("output_path"):
        rp = REPO / str(unit["output_path"]).replace("\\", "/")
        if rp.is_file() and rp.stat().st_size > 0:
            doc = load(rp)
            if "__err__" in doc:
                r["receipt"] = {"state": "UNPARSEABLE", "err": doc["__err__"]}
            else:
                rv = doc.get("reviewer") or {}
                r["receipt"] = {
                    "state": doc.get("state"),
                    "sentinel": doc.get("sentinel"),
                    "reviewer_verdict": rv.get("verdict"),
                    "independent": rv.get("independent"),
                    "failure": (doc.get("failure") or {}).get("classification"),
                    "evidence_n": len(doc.get("evidence") or []),
                    "tests_n": len(doc.get("tests") or []),
                    "bytes": rp.stat().st_size,
                }
        else:
            r["receipt"] = {"state": "MISSING"}
    # manifest rows vs live
    man_p = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    if man_p.is_file():
        man = load(man_p)
        rows = [a for a in (man.get("artifacts") or []) if a.get("unit_id") == uid]
        bad = []
        for a in rows:
            ap = REPO / str(a.get("path", "")).replace("\\", "/")
            if not ap.is_file():
                bad.append({"path": a.get("path"), "why": "absent"})
                continue
            sha, nb = digest_file(ap)
            if sha != a.get("sha256"):
                bad.append({"path": a.get("path"), "why": "sha-mismatch",
                            "manifest": a.get("sha256"), "live": sha})
            elif a.get("present") is not True:
                bad.append({"path": a.get("path"), "why": "present-flag-false"})
        r["manifest"] = {"rows": len(rows), "bad_rows": bad}
    else:
        r["manifest"] = {"rows": 0, "bad_rows": [], "why": "no-manifest"}
    # SUBAGENT-RETURN status
    ret_p = pdir / "SUBAGENT-RETURN.json"
    if ret_p.is_file():
        ret = load(ret_p)
        r["return_status"] = ret.get("status") or ret.get("state") if isinstance(ret, dict) else "UNPARSEABLE"
    else:
        r["return_status"] = "no-return-file"
    report[uid] = r

print(json.dumps(report, indent=1))
