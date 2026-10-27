import json, hashlib, subprocess, sys, os
from pathlib import Path
from jsonschema import Draft202012Validator

REPO = Path.home() / "p2-g1"
IDS = ["IMP-0035","IMP-0036","IMP-0037","IMP-0038","IMP-0041","IMP-0044",
       "IMP-0051","IMP-0068","IMP-0070","IMP-0084","IMP-0090","IMP-0093"]
PROBES_ROOT = REPO / "command-center/p2-wave/probes"

def norm_sha(p: Path) -> str:
    data = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()

cat = json.load(open(REPO/"command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
catidx = {u["id"]: u for u in cat["work_units"]}
receipt_schema = json.load(open(REPO/"command-center/schema/receipt.schema.json", encoding="utf-8"))
rsv = Draft202012Validator(receipt_schema)

results = {}
for uid in IDS:
    cu = catidx.get(uid, {})
    out_path = cu.get("output_path")
    res = {"id": uid, "checks": {}, "fails": []}
    art = REPO / out_path if out_path else None
    # 1. artifact exists/non-empty/parses/not-self-blocked
    if art is None:
        res["fails"].append("catalog-entry-missing")
    elif not art.exists():
        res["fails"].append(f"artifact-missing::{out_path}")
    elif art.stat().st_size == 0:
        res["fails"].append(f"artifact-empty::{out_path}")
    else:
        try:
            r = json.load(open(art, encoding="utf-8"))
            res["receipt"] = {"state": r.get("state"), "reviewer": r.get("reviewer")}
            st = (r.get("state") or "").upper()
            if st in ("BLOCKED", "FAILED"):
                res["fails"].append(f"artifact-self-declared::{st}")
        except Exception as e:
            res["fails"].append(f"artifact-unparseable::{e}")
            r = None
    # 2. schema validation (receipt schema)
    if r is not None:
        errs = list(rsv.iter_errors(r))
        res["checks"]["receipt_schema_errors"] = len(errs)
        if errs:
            first = sorted(errs, key=lambda e: (len(list(e.path)), list(e.path)))
            res["fails"].append(f"receipt-schema-invalid({len(errs)}): " + "; ".join(
                f"{list(e.path) or '<root>'}: {e.message[:90]}" for e in first[:3]))
    # 3. manifest sha256 match (CRLF->LF)
    man_p = PROBES_ROOT / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if not man_p.exists():
        res["fails"].append("manifest-missing")
    else:
        man = json.load(open(man_p, encoding="utf-8"))
        rows = man.get("artifacts", [])
        row = next((x for x in rows if x.get("path") == out_path), None)
        if row is None:
            res["fails"].append("manifest-no-row-for-output_path")
        else:
            live = norm_sha(art)
            res["checks"]["manifest_sha_match"] = (live == row.get("sha256"))
            if live != row.get("sha256"):
                res["fails"].append(f"manifest-sha-mismatch::live={live[:12]} manifest={str(row.get('sha256'))[:12]}")
    # 4. live probes: run every probe*.py in probes/<id>/, require rc 0
    pdir = PROBES_ROOT / uid
    probes = sorted(pdir.glob("probe*.py")) if pdir.exists() else []
    rc_list, markers = [], []
    for pr in probes:
        cp = subprocess.run([sys.executable, "-I", str(pr)], cwd=REPO,
                            capture_output=True, text=True, timeout=600)
        rc_list.append(cp.returncode)
        markers.append({"probe": pr.name, "rc": cp.returncode,
                        "stdout_tail": cp.stdout.strip().splitlines()[-1][:120] if cp.stdout.strip() else "",
                        "stderr_tail": cp.stderr.strip().splitlines()[-1][:160] if cp.stderr.strip() else ""})
        if cp.returncode != 0:
            res["fails"].append(f"probe-fail::{pr.name}::rc={cp.returncode}")
    res["probes"] = markers
    results[uid] = res

json.dump(results, open(REPO/"_reviewer10w2-rerun2/battery_out.json","w",encoding="utf-8"), indent=1)
for uid in IDS:
    r = results[uid]
    fails = r["fails"]
    print(f"=== {uid} :: {'PASS' if not fails else 'FAIL'}")
    for f in fails: print("   FAIL:", f)
    for m in r.get("probes", []): print(f"   probe {m['probe']} rc={m['rc']} :: {m['stdout_tail'] or m['stderr_tail']}")
