"""Final verification battery for shard14-w3: measure tool + estate gate + strict schema
+ manifest sha + reviewer closure + sentinel + owner-gate check, per unit."""
import json, sys, subprocess, hashlib
sys.path.insert(0, "_p2shard14-w3")
from pathlib import Path
from jsonschema import Draft202012Validator
import repair_lib as L
import repair_main as M

ids = L.IDS
results = {}
allok = True
for uid in ids:
    r = {}
    # 1. canonical delivery measure (fresh process)
    import os as _os
    _env = _os.environ.copy()
    _env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run([sys.executable, "-B", "command-center/p2-wave/_measure_one_delivered.py", uid],
                       capture_output=True, text=True, cwd=str(L.REPO), env=_env)
    out = (p.stdout + p.stderr).strip().splitlines()
    r["measure_rc"] = p.returncode
    r["measure_verdict"] = out[-1] if out else ""
    # 2. estate admission gate
    p2 = subprocess.run([sys.executable, "-B", "command-center/receipt_validate.py",
                         "command-center/receipts/%s.json" % uid],
                        capture_output=True, text=True, cwd=str(L.REPO), env=_env)
    o2 = (p2.stdout + p2.stderr).strip().splitlines()
    r["admission_rc"] = p2.returncode
    r["admission"] = (o2[0] if o2 else "")[:80]
    # 3. strict receipt_core
    doc = json.loads(L.receipt_path(uid).read_text(encoding="utf-8"))
    errs = list(M.VAL.iter_errors(doc))
    r["strict_schema_errors"] = len(errs)
    # 4. manifest sha row
    man = json.loads(L.manifest_path(uid).read_text(encoding="utf-8"))
    sha, n = L.norm_digest(L.receipt_path(uid))
    row = next((a for a in man.get("artifacts", []) if a.get("unit_id") == uid), None)
    r["manifest_sha_ok"] = bool(row and row.get("sha256") == sha and row.get("present") is True
                                and str(row.get("path")).replace("\\", "/") == "command-center/receipts/%s.json" % uid)
    # 5. reviewer closure + state
    rev = doc.get("reviewer") or {}
    r["state"] = doc.get("state")
    r["reviewer_pass"] = rev.get("verdict") == "PASS"
    r["reviewer_independent"] = rev.get("independent") is True
    # 6. sentinel present in text
    entry = L.catalog_entry(uid) or {}
    sent = entry.get("completion_sentinel") or ""
    r["sentinel_in_text"] = bool(sent) and sent in L.receipt_path(uid).read_text(encoding="utf-8")
    # 7. owner-gate
    r["owner_gated"] = bool(entry.get("owner_approval_required"))
    ok = (r["measure_rc"] == 0 and r["admission_rc"] == 0 and r["strict_schema_errors"] == 0
          and r["manifest_sha_ok"] and r["state"] == "SUCCESS" and r["reviewer_pass"]
          and r["reviewer_independent"] and r["sentinel_in_text"])
    r["ALL_GREEN"] = ok
    allok = allok and ok
    results[uid] = r
    print("%-9s measure=%s admission=%s strict=%d manifest=%s state=%s revPASS=%s indep=%s sentinel=%s gated=%s => %s"
          % (uid, r["measure_rc"], r["admission_rc"], r["strict_schema_errors"], r["manifest_sha_ok"],
             r["state"], r["reviewer_pass"], r["reviewer_independent"], r["sentinel_in_text"],
             r["owner_gated"], "GREEN" if ok else "NOT-GREEN"))
    if not ok:
        for e in errs[:4]:
            print("    strict:", list(e.path), str(e.message)[:120])
        print("    measure:", r["measure_verdict"][:120])
        print("    admission:", r["admission"][:120])
out = L.REPO / "_p2shard14-w3" / "final-verify.json"
out.write_text(json.dumps(results, indent=1), encoding="utf-8")
print("FINAL:", "12/12 ALL-GREEN" if allok else "INCOMPLETE")
