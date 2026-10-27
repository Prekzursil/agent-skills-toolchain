#!/usr/bin/env python3
"""Part 2: RES-0137 pass-2 evidence refresh; rewrite manifests + returns for 0112/0137."""
import json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

WS = Path("C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(WS / "command-center/p2-wave"))
import _p2lib as P  # noqa: E402
from _s7w2lib import write_unit_manifest  # noqa: E402
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
CAT = json.load(open(WS / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
BYID = {u["id"]: u for u in CAT["work_units"]}

def art_path(uid):
    return WS.joinpath(*BYID[uid]["output_path"].split("/"))

def rel(uid):
    return BYID[uid]["output_path"]

def run_probe(uid, script):
    r = subprocess.run([sys.executable, "-B", str(WS / "command-center/p2-wave/probes" / uid / script)],
                       cwd=str(WS), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()

# ---- RES-0137 pass-2: live probe outputs into evidence + consumers ----
rc1, out1 = run_probe("RES-0137", "probe1_lineage_and_contract.py")
rc2, out2 = run_probe("RES-0137", "probe2_negative_control.py")
assert rc1 == 0 and rc2 == 0, (rc1, rc2, out1[-400:], out2[-400:])
a = art_path("RES-0137")
doc = json.loads(a.read_text(encoding="utf-8"))
doc["evidence"][0]["probes"][0]["raw_output"] = out1[-3000:]
doc["evidence"][0]["probes"][1]["raw_output"] = out2[-3000:]
for consumer in doc["downstream_consumers"]:
    tail = out1 if "probe1" in consumer["consumer"] else out2
    consumer["probe"]["raw_output"] = tail[-3000:]
errs = P.validate(doc, BYID["RES-0137"]["output_schema"])
assert not errs, errs[:6]
a.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print("RES-0137 pass-2 refreshed;", a.stat().st_size, "B; probes exit 0/0")

# ---- manifests + returns for the two artifacts that changed today ----
def norm_sha(p):
    import hashlib
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

for uid in ["RES-0112", "RES-0137"]:
    ap = art_path(uid)
    op = rel(uid)
    prow = WS / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    old = json.loads(prow.read_text(encoding="utf-8"))
    rows = [(str(x["path"]).replace(chr(92), "/"), str(x.get("role") or "supporting"))
            for x in old.get("artifacts", [])]
    write_unit_manifest(uid, rows)
    man = json.loads(prow.read_text(encoding="utf-8"))
    ret_p = prow.parent / "SUBAGENT-RETURN.json"
    ret = json.loads(ret_p.read_text(encoding="utf-8"))
    for x in ret.get("artifacts", []):
        if str(x.get("path", "")).replace(chr(92), "/") == op:
            x["bytes"] = ap.stat().st_size
            x["sha256"] = norm_sha(ap)
            x["exists"] = True
    ret["wave2_resume"] = {"at": NOW, "by": "builder shard 18 wave 2",
                           "note": ("artifact refreshed on resume (0112: gate citations re-anchored; "
                                    "0137: rebuilt to probe contract, stage contract preserved as sidecar); "
                                    "named probes re-run exit 0 on the live tree")}
    ret_p.write_text(json.dumps(ret, indent=1) + "\n", encoding="utf-8")
    rows_ok = any(x.get("sha256") == norm_sha(ap) and x.get("present") is True
                  for x in man.get("artifacts", []) if x.get("unit_id") == uid)
    print(uid, "manifest sha-match:", rows_ok)
