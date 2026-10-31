#!/usr/bin/env python3
"""Refresh receipt/return artifact rows for edited artifacts, then sweep the delivery gate x12."""
import hashlib, json, subprocess, sys
from pathlib import Path

WS = Path("C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(WS / "command-center/p2-wave"))
import _p2lib as P  # noqa: E402
CAT = json.load(open(WS / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
BYID = {u["id"]: u for u in CAT["work_units"]}
IDS = ["RES-0112","RES-0114","RES-0128","RES-0131","RES-0132","RES-0137",
       "RES-0140","RES-0141","RES-0144","RES-0148","RES-0149","RES-0150"]

def apath(uid):
    return WS.joinpath(*BYID[uid]["output_path"].split("/"))

def nsha(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

for uid in IDS:
    ap = apath(uid)
    # SUBAGENT-RETURN artifact row
    rp = WS / "command-center/p2-wave/probes" / uid / "SUBAGENT-RETURN.json"
    ret = json.loads(rp.read_text(encoding="utf-8"))
    for x in ret.get("artifacts", []):
        if str(x.get("path", "")).replace("\\", "/") == BYID[uid]["output_path"]:
            x["bytes"], x["sha256"], x["exists"] = ap.stat().st_size, nsha(ap), True
    rp.write_text(json.dumps(ret, indent=1) + "\n", encoding="utf-8")
    # receipt artifact row
    cp = WS / "command-center/receipts" / (uid + ".json")
    rec = json.loads(cp.read_text(encoding="utf-8"))
    rec["artifacts"] = [P.art(BYID[uid]["output_path"], "primary")]
    errs = P.validate(rec, "command-center/schema/receipt.schema.json")
    assert not errs, (uid, errs[:3])
    cp.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(uid, "receipt+return rows refreshed; receipt state:", rec["state"])

print("---- delivery gate sweep ----")
green = 0
for uid in IDS:
    r = subprocess.run([sys.executable, "-I", str(WS / "command-center/p2-wave/_measure_one_delivered.py"), uid],
                       cwd=str(WS), capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "", "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""), "SYSTEM32": ""} if False else None,
                       timeout=3600)
    out = (r.stdout or "") + (r.stderr or "")
    line = [l for l in out.splitlines() if l.startswith(("SUCCESS:delivered", "FAILED:delivered"))]
    tag = line[-1] if line else "no-verdict"
    green += tag.startswith("SUCCESS")
    print(uid, "->", tag)
print("GREEN %d/12" % green)
