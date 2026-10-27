import hashlib, json, subprocess, sys
from pathlib import Path
WS = Path("C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(WS / "command-center/p2-wave"))
import _p2lib as P
from _s7w2lib import write_unit_manifest
CAT = json.load(open(WS / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
BYID = {u["id"]: u for u in CAT["work_units"]}
IDS = ["RES-0112","RES-0114","RES-0128","RES-0131","RES-0132","RES-0137",
       "RES-0140","RES-0141","RES-0144","RES-0148","RES-0149","RES-0150"]
def apath(uid): return WS.joinpath(*BYID[uid]["output_path"].split("/"))
def nsha(p): return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
for uid in IDS:
    ap = apath(uid)
    prow = WS / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    old = json.loads(prow.read_text(encoding="utf-8"))
    rows = [(str(x["path"]).replace(chr(92), "/"), str(x.get("role") or "supporting"))
            for x in old.get("artifacts", [])]
    if not any(r[0] == BYID[uid]["output_path"] for r in rows):
        rows.insert(0, (BYID[uid]["output_path"], "primary"))
    write_unit_manifest(uid, rows)
    man = json.loads(prow.read_text(encoding="utf-8"))
    ok = any(x.get("sha256") == nsha(ap) and x.get("present") is True
             and str(x.get("path", "")).replace(chr(92), "/") == BYID[uid]["output_path"]
             for x in man.get("artifacts", []))
    rp = prow.parent / "SUBAGENT-RETURN.json"
    ret = json.loads(rp.read_text(encoding="utf-8"))
    for x in ret.get("artifacts", []):
        if str(x.get("path", "")).replace(chr(92), "/") == BYID[uid]["output_path"]:
            x["bytes"], x["sha256"], x["exists"] = ap.stat().st_size, nsha(ap), True
    ret.setdefault("wave2_resume", {})["envelope_completed"] = True
    rp.write_text(json.dumps(ret, indent=1) + "\n", encoding="utf-8")
    cp = WS / "command-center/receipts" / (uid + ".json")
    rec = json.loads(cp.read_text(encoding="utf-8"))
    rec["artifacts"] = [P.art(BYID[uid]["output_path"], "primary")]
    errs = P.validate(rec, "command-center/schema/receipt.schema.json")
    assert not errs, (uid, errs[:3])
    cp.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(uid, "manifest-match:", ok, "| receipt BLOCKED:", rec["state"] == "BLOCKED")
print("---- final delivery-gate sweep ----")
green = 0
for uid in IDS:
    r = subprocess.run([sys.executable, "-I", str(WS / "command-center/p2-wave/_measure_one_delivered.py"), uid],
                       cwd=str(WS), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
    out = (r.stdout or "") + (r.stderr or "")
    line = [l for l in out.splitlines() if l.startswith(("SUCCESS:delivered", "FAILED:delivered"))]
    tag = line[-1] if line else "no-verdict"
    green += tag.startswith("SUCCESS")
    print(uid, "->", tag)
    if not tag.startswith("SUCCESS"):
        print(out[-1200:])
print("GREEN %d/12" % green)
