"""Independent reviewer battery, wave2 shard12. Fresh-context re-verification.

Checks per unit (ALL must hold for CONFIRM):
  C1 catalog entry (output_path, output_schema, dependencies)
  C2 receipt exists, non-empty, parses
  C3 receipt not self-declared BLOCKED/FAILED
  C4 manifest receipt-row sha256 (CRLF->LF normalized) == live artifact
  C5 supporting manifest rows sha256 (reported; mismatch = flag)
  C6 live probe re-run: every probes/<u>/probe*.py exits 0
  C7 jsonschema validation against receipt_core (physical, registry-resolved)
  C8 closure rule: state==SUCCESS -> reviewer.verdict==PASS and independent==true
Writes _rv2_independent_results.json.
"""
import hashlib, json, os, subprocess, sys
from pathlib import Path
from urllib.parse import unquote

W = Path.home() / "p2-g1"
UNITS = ["IMP-0165", "IMP-0194", "IMP-0195", "IMP-0198", "IMP-0202", "IMP-0204",
         "IMP-0218", "IMP-0219", "IMP-0221", "IMP-0222", "IMP-0224", "IMP-0228"]


def sha_norm(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


# --- schema: physical receipt_core with file:// registry ---
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

phys = json.loads((W / "platform/schema/receipt.schema.json").read_text(encoding="utf-8"))


def retrieve(uri: str) -> Resource:
    p = unquote(uri)
    if p.startswith("file:///"):
        p = p[len("file:///"):]
    elif p.startswith("file://"):
        p = p[len("file://"):]
    data = json.loads(Path(p).read_text(encoding="utf-8"))
    return Resource.from_contents(data, default_specification=DRAFT202012)


registry = Registry(retrieve=retrieve)
root = {"$ref": "#/$defs/receipt_core", "$defs": phys["$defs"],
        "$schema": phys.get("$schema", "https://json-schema.org/draft/2020-12/schema")}
validator = Draft202012Validator(root, registry=registry)

cat = json.loads((W / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
cat_by_id = {u["id"]: u for u in cat["work_units"]}

env = dict(os.environ)
env["PYTHONDONTWRITEBYTECODE"] = "1"

results = []
for uid in UNITS:
    R = {"unit": uid, "checks": {}, "probe_results": [], "sha_rows": [], "schema_errors": []}
    # C1 catalog
    ent = cat_by_id.get(uid)
    R["checks"]["catalog_entry"] = bool(ent and ent.get("output_path") and ent.get("output_schema") and "dependencies" in ent)
    if not ent:
        R["verdict"] = "FAIL"
        R["fail_reason"] = "catalog entry missing"
        results.append(R)
        continue
    out_rel = ent["output_path"]
    out_path = W / out_rel
    # C2 receipt exists/non-empty/parses
    if not out_path.exists() or out_path.stat().st_size == 0:
        R["verdict"] = "FAIL"
        R["fail_reason"] = "receipt missing/empty at " + out_rel
        results.append(R)
        continue
    try:
        receipt = json.loads(out_path.read_text(encoding="utf-8"))
        R["checks"]["receipt_parses"] = True
    except Exception as e:
        R["verdict"] = "FAIL"
        R["fail_reason"] = "receipt does not parse: " + repr(e)
        results.append(R)
        continue
    # C3 not self-blocked/failed
    R["state"] = receipt.get("state")
    R["checks"]["not_self_blocked"] = receipt.get("state") not in ("BLOCKED", "FAILED")
    # C4/C5 manifest rows
    mpath = W / ("command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json")
    if not mpath.exists():
        R["verdict"] = "FAIL"
        R["fail_reason"] = "UNIT-ARTIFACT-MANIFEST.json missing"
        results.append(R)
        continue
    man = json.loads(mpath.read_text(encoding="utf-8"))
    live_sha = sha_norm(out_path)
    R["live_sha256"] = live_sha
    row_match = False
    for a in man.get("artifacts", []):
        ap = W / a["path"]
        ok = False
        if ap.exists():
            ok = (sha_norm(ap) == a.get("sha256"))
        R["sha_rows"].append({"path": a["path"], "match": ok})
        if Path(a["path"]) == Path(out_rel):
            row_match = ok
    R["checks"]["manifest_receipt_sha_match"] = row_match
    R["checks"]["supporting_rows_all_match"] = all(r["match"] for r in R["sha_rows"])
    # C6 probes re-run
    pdir = W / ("command-center/p2-wave/probes/" + uid)
    probes = sorted(pdir.glob("probe*.py"))
    all0 = True
    for p in probes:
        rel = str(p.relative_to(W))
        try:
            cp = subprocess.run([sys.executable, "-B", rel], cwd=str(W), env=env,
                                capture_output=True, text=True, timeout=300)
            rc = cp.returncode
            tail = (cp.stdout or cp.stderr or "")[-200:]
        except Exception as e:
            rc = -999
            tail = str(e)[:200]
        R["probe_results"].append({"probe": p.name, "exit": rc})
        if rc != 0:
            all0 = False
            R["probe_fail_tail"] = tail
    R["checks"]["probes_exit0"] = all0 and len(probes) > 0
    # C7 schema validation
    errs = sorted(validator.iter_errors(receipt), key=lambda e: list(map(str, e.absolute_path)))
    R["schema_error_count"] = len(errs)
    for e in errs[:8]:
        R["schema_errors"].append("/".join(map(str, e.absolute_path)) or "<root>" + ": " + e.message[:160])
    R["checks"]["output_schema_valid"] = (len(errs) == 0)
    # C8 closure rule
    rev = receipt.get("reviewer") or {}
    R["reviewer_verdict"] = rev.get("verdict")
    R["reviewer_independent"] = rev.get("independent")
    if receipt.get("state") == "SUCCESS":
        R["checks"]["closure_rule"] = (rev.get("verdict") == "PASS" and rev.get("independent") is True)
    else:
        R["checks"]["closure_rule"] = True
    # verdict
    failed = [k for k, v in R["checks"].items() if not v]
    if failed:
        R["verdict"] = "FAIL"
        R["fail_reason"] = "failing checks: " + ", ".join(failed)
    else:
        R["verdict"] = "CONFIRM"
    results.append(R)

out = W / "_shard12-w2/_rv2_independent_results.json"
out.write_text(json.dumps(results, indent=1), encoding="utf-8")
for R in results:
    print(R["unit"], "|", R.get("verdict"), "| state:", R.get("state"),
          "| probes:", [(p["probe"], p["exit"]) for p in R.get("probe_results", [])],
          "| schema_errs:", R.get("schema_error_count"),
          "| supp_rows_ok:", R["checks"].get("supporting_rows_all_match"))
    if R.get("fail_reason"):
        print("   FAIL:", R["fail_reason"])
    for e in R.get("schema_errors", [])[:4]:
        print("   schema:", e)
print("WROTE", out)
