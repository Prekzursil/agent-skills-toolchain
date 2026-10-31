#!/usr/bin/env python3
import hashlib, importlib.util, json, os, subprocess, sys
from pathlib import Path
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
PROBES = REPO / "command-center/p2-wave/probes"
MY12 = ["ADV-0005","ADV-0010","ADV-0014","ADV-0015","ADV-0018","ADV-0019",
        "ADV-0022","ADV-0023","ADV-0024","ADV-0028","ADV-0029","ADV-0037"]
spec = importlib.util.spec_from_file_location("rsg", REPO / "platform/lib/receipt_schema_gate.py")
rsg = importlib.util.module_from_spec(spec); sys.modules["rsg"] = rsg; spec.loader.exec_module(rsg)
cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u.get("id"): u for u in cat["work_units"]}

def lf_sha(p):
    return hashlib.sha256(Path(p).read_bytes().replace(b"\r\n", b"\n")).hexdigest()

def run_py(script):
    env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "TEMP", "TMP") if k in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    r = subprocess.run([sys.executable, "-I", "-B", str(script)],
                       capture_output=True, text=True, timeout=600, cwd=str(REPO), env=env)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()

allok = True
for uid in MY12:
    u = byid[uid]
    out_rel = u["output_path"].replace("\\", "/")
    art = REPO / out_rel
    doc = json.loads(art.read_text(encoding="utf-8"))
    rp = REPO / ("command-center/receipts/" + uid + ".json")
    r = json.loads(rp.read_text(encoding="utf-8"))
    # artifact predicate
    a_ok = (art.stat().st_size >= 1024
            and str(doc.get("state") or "").upper() not in ("BLOCKED", "FAILED", "SEVERED", "TIMEOUT"))
    # manifest sha
    man = json.loads((PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
    sha_ok = any(str(a.get("path") or "").replace("\\", "/") == out_rel
                 and a.get("sha256") == lf_sha(art) and a.get("present") is True
                 for a in man.get("artifacts", []))
    # probes
    probes = {}
    for s in sorted(PROBES.joinpath(uid).glob("probe[12]_*.py")):
        rc, out = run_py(s)
        probes[s.name] = rc
    probes_ok = all(v == 0 for v in probes.values())
    # receipt posture
    rev = r.get("reviewer") or {}
    closed = (r.get("state") == "SUCCESS"
              and rev.get("verdict") == "PASS" and rev.get("independent") is True
              and str(r.get("unit_id")) == uid)
    # program admission + gate
    v = subprocess.run([sys.executable, "-I", str(REPO / "command-center/receipt_validate.py"),
                        str(rp)], capture_output=True, text=True, cwd=str(REPO))
    res = rsg.evaluate_gate_a(r, repo_root=str(REPO), verify_filesystem=True)
    adm = v.returncode == 0
    orig = (r.get("extensions") or {}).get("builder_receipt_original")
    orig_ok = isinstance(orig, dict) and bool(orig.get("state"))
    verdict = "CLOSED-GREEN" if (a_ok and sha_ok and probes_ok and closed and adm and res.complete and orig_ok) \
        else ("FAIL-EXPECTED" if uid == "ADV-0037" and not probes_ok and r.get("state") == "BLOCKED" else "PROBLEM")
    if verdict == "PROBLEM":
        allok = False
    print("{:9} art={} sha={} probes={} closed={} admit={} gate12={} orig={} -> {}".format(
        uid, a_ok, sha_ok, probes_ok, closed, adm, res.complete, orig_ok, verdict))
    if verdict == "FAIL-EXPECTED":
        bad = [k for k, v2 in probes.items() if v2 != 0]
        print("          ADV-0037 receipt state:", r.get("state"),
              "| reviewer:", r.get("reviewer"),
              "| failing probes:", bad)

# corpus-level collateral check
import glob
succ = bloc = 0
for f in glob.glob(str(REPO / "command-center/receipts/*.json")):
    try:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:
        continue
    if d.get("state") == "SUCCESS":
        succ += 1
    elif d.get("state") == "BLOCKED":
        bloc += 1
print("")
print("corpus: SUCCESS =", succ, "| BLOCKED =", bloc, "(pre-session: 1055 / 97)")
print("ALL-OK" if allok else "PROBLEMS-PRESENT")
