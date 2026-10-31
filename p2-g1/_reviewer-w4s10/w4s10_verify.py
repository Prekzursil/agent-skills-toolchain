"""w4s10 independent reviewer - Phase A read-only verification battery."""
from __future__ import annotations
import hashlib, json, os, subprocess, sys, time
from pathlib import Path

HOME = Path(r"C:/Users/Prekzursil")
G1 = HOME / "p2-g1"
AI = HOME / "source/ast-integrate"
UNITS = ["IMP-0189", "IMP-0194", "IMP-0195", "IMP-0198", "IMP-0202",
         "IMP-0204", "IMP-0207", "IMP-0219", "IMP-0223", "IMP-0224",
         "IMP-0228", "IMP-0229"]
DECLARED_SCHEMA = "command-center/schema/receipt.schema.json"

sys.path.insert(0, str(AI / "platform/lib"))
os.environ["AST_INTEGRATE_ROOT"] = str(G1)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
import schema_resolver  # noqa: E402

def lf_sha(p):
    return hashlib.sha256(Path(p).read_bytes().replace(b"\r\n", b"\n")).hexdigest()

def run(cmd, cwd, timeout=180):
    t0 = time.monotonic()
    pr = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                        errors="replace", timeout=timeout,
                        env=dict(os.environ, AST_INTEGRATE_ROOT=str(G1),
                                 PYTHONDONTWRITEBYTECODE="1"))
    return {"cmd": " ".join(cmd), "rc": pr.returncode,
            "sec": round(time.monotonic() - t0, 2),
            "out_tail": pr.stdout[-900:], "err_tail": pr.stderr[-900:]}

results = {}
CAT = {u["id"]: u for u in json.loads((G1 / "command-center/WORK-UNIT-CATALOG.json").read_bytes().decode("utf-8"))["work_units"]}

for uid in UNITS:
    R = {"unit": uid, "checks": {}, "notes": []}
    R["_cat_sentinel"] = (CAT.get(uid) or {}).get("completion_sentinel")
    rp = G1 / ("command-center/receipts/" + uid + ".json")
    if not rp.is_file() or rp.stat().st_size == 0:
        R["checks"]["artifact_exists_nonempty"] = False
        results[uid] = R
        continue
    R["checks"]["artifact_exists_nonempty"] = True
    try:
        receipt = json.loads(rp.read_bytes().decode("utf-8"))
        R["checks"]["artifact_parses"] = True
    except Exception as e:
        R["checks"]["artifact_parses"] = False
        R["notes"].append("parse: " + repr(e))
        results[uid] = R
        continue
    R["receipt_bytes"] = rp.stat().st_size
    R["receipt_sha256_lf"] = lf_sha(rp)
    state = receipt.get("state")
    R["state"] = state
    R["checks"]["not_self_blocked"] = state not in ("BLOCKED", "FAILED", "TIMEOUT", "SEVERED")
    R["checks"]["state_is_SUCCESS"] = state == "SUCCESS"
    sent = str(receipt.get("sentinel") or receipt.get("completion_sentinel") or "").strip()
    R["checks"]["sentinel_present"] = bool(sent)
    R["sentinel"] = sent
    R["checks"]["sentinel_binds_catalog"] = sent == str((R.get("_cat_sentinel") or sent))
    R["checks"]["unit_id_matches"] = receipt.get("unit_id") == uid
    rev = receipt.get("reviewer") or {}
    R["current_reviewer"] = dict((k, rev.get(k)) for k in ("reviewer_id", "verdict", "independent", "fresh_context"))
    R["self_review_suspect"] = bool(rev.get("reviewer_id") and uid in str(rev.get("reviewer_id")))
    mp = G1 / ("command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json")
    man = json.loads(mp.read_bytes().decode("utf-8"))
    mres, probe_files = [], []
    for row in man["artifacts"]:
        rel = row["path"]
        ap = G1 / rel
        present = ap.is_file() and ap.stat().st_size > 0
        sha_ok = present and lf_sha(ap) == row["sha256"]
        mres.append({"path": rel, "role": row.get("role"), "present": present, "sha_match": sha_ok})
        if row.get("role") == "named-probe":
            probe_files.append(rel)
    R["checks"]["manifest_all_present"] = all(r["present"] for r in mres)
    R["checks"]["manifest_all_sha_match"] = all(r["sha_match"] for r in mres)
    R["manifest_rows"] = len(mres)
    R["manifest_bad"] = [r["path"] for r in mres if not (r["present"] and r["sha_match"])]
    probes_ok, probes = True, []
    for pf in probe_files:
        r = run([sys.executable, "-B", pf], cwd=G1)
        ok = (r["rc"] == 0) and ("SUCCESS:" in r["out_tail"])
        probes_ok = probes_ok and ok
        probes.append(dict(r, ok=ok))
    R["checks"]["probes_all_exit0"] = probes_ok
    R["probe_runs"] = [{"cmd": p["cmd"], "rc": p["rc"], "ok": p["ok"],
                        "success_line": next((l for l in p["out_tail"].splitlines() if "SUCCESS:" in l), "")[:170]}
                       for p in probes]
    try:
        errs = schema_resolver.validate_artifact(receipt, DECLARED_SCHEMA)
        R["checks"]["output_schema_valid"] = not errs
        R["schema_errors"] = errs[:12]
    except Exception as e:
        R["checks"]["output_schema_valid"] = False
        R["schema_errors"] = ["resolver exception: " + type(e).__name__ + ": " + str(e)]
    adm = run([sys.executable, "-B", "command-center/receipt_validate.py",
               "command-center/receipts/" + uid + ".json"], cwd=G1)
    R["admission_rc"] = adm["rc"]
    R["admission_out"] = (adm["out_tail"] + adm["err_tail"])[-240:]
    R["checks"]["admission_accept"] = ("ACCEPT" in adm["out_tail"]) and adm["rc"] == 0
    results[uid] = R

out = G1 / "_reviewer-w4s10/w4s10-rerun/phase_a_results.json"
out.write_text(json.dumps(results, indent=1), encoding="utf-8")
print("wrote", out)
for uid, R in results.items():
    c = R["checks"]
    fails = [k for k, v in c.items() if v is False]
    tag = "ALL-PASS" if not fails else "FAIL:" + ",".join(fails)
    cr = (R.get("current_reviewer") or {}).get("reviewer_id")
    print(uid, tag, "rows=" + str(R.get("manifest_rows")),
          "reviewer=" + str(cr), "self_suspect=" + str(R.get("self_review_suspect")))
