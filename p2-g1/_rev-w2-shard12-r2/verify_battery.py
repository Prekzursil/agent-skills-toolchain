#!/usr/bin/env python3
"""Independent reviewer battery, wave2 shard12 r2 (fresh context, 2026-10-26).

My own re-derivation of the unit contract. Pure verification - writes NOTHING
outside this scratch dir. Closure is a separate deliberate step.

Per unit, ALL must hold:
  A catalog entry with output_path/output_schema/dependencies
  B receipt at output_path: exists, non-empty, parses, unit_id match,
    state not BLOCKED/FAILED, sentinel == SUCCESS:<id>
  C manifest UNIT-ARTIFACT-MANIFEST.json exists; PRIMARY row sha256
    (CRLF->LF normalized) == live artifact sha256
  D supporting manifest rows also match live files (strict, as prior run)
  E every probes/<id>/probe*.py re-run live by ME exits 0 (need >=2 probes)
  F output_schema valid under TWO instruments:
      F1 platform/lib/schema_resolver.validate_artifact (canonical resolver)
      F2 direct Draft2020-12 against platform/schema/receipt.schema.json#/$defs/receipt_core
  G closure rule: state==SUCCESS -> reviewer.verdict==PASS and independent is true
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

W = Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = ["IMP-0165", "IMP-0194", "IMP-0195", "IMP-0198", "IMP-0202", "IMP-0204",
         "IMP-0218", "IMP-0219", "IMP-0221", "IMP-0222", "IMP-0224", "IMP-0228"]
OUT = W / "_rev-w2-shard12-r2" / "verify_results.json"


def sha_norm(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


# --- F2: direct physical receipt_core validator -----------------------------
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

phys = json.loads((W / "platform/schema/receipt.schema.json").read_text(encoding="utf-8"))


def retrieve(uri: str) -> Resource:
    p = unquote(uri)
    for pre in ("file:///", "file://"):
        if p.startswith(pre):
            p = p[len(pre):]
            break
    data = json.loads(Path(p).read_text(encoding="utf-8"))
    return Resource.from_contents(data, default_specification=DRAFT202012)


registry = Registry(retrieve=retrieve)
direct_validator = Draft202012Validator(
    {"$ref": "#/$defs/receipt_core", "$defs": phys["$defs"],
     "$schema": phys.get("$schema", "https://json-schema.org/draft/2020-12/schema")},
    registry=registry)

# --- F1: canonical repo resolver --------------------------------------------
sys.path.insert(0, str(W / "platform" / "lib"))
import schema_resolver as sr  # noqa: E402

cat = json.loads((W / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
cat_by_id = {u["id"]: u for u in cat["work_units"]}

env = dict(os.environ)
env["PYTHONDONTWRITEBYTECODE"] = "1"

results = []
for uid in UNITS:
    R = {"unit": uid, "checks": {}, "probe_results": [], "sha_rows": [],
         "resolver_errors": [], "direct_errors": [], "warnings": []}

    def fail(reason):
        R["verdict"] = "FAIL"
        R["fail_reason"] = reason
        results.append(R)

    ent = cat_by_id.get(uid)
    if not (ent and ent.get("output_path") and ent.get("output_schema") and "dependencies" in ent):
        fail("catalog entry missing/incomplete")
        continue
    R["checks"]["catalog_entry"] = True
    out_rel = ent["output_path"]
    out_path = W / out_rel

    if not out_path.is_file() or out_path.stat().st_size == 0:
        fail(f"receipt missing/empty: {out_rel}")
        continue
    try:
        receipt = json.loads(out_path.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"receipt does not parse: {e!r}")
        continue
    R["checks"]["receipt_parses"] = True
    R["checks"]["unit_id_match"] = (receipt.get("unit_id") == uid)
    R["state"] = receipt.get("state")
    R["checks"]["not_self_blocked"] = R["state"] not in ("BLOCKED", "FAILED")
    want_sentinel = f"SUCCESS:{uid}"
    R["checks"]["sentinel_match"] = (receipt.get("sentinel") == want_sentinel
                                     and str(ent.get("completion_sentinel")) == want_sentinel)

    # C/D manifest rows
    mpath = W / f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
    if not mpath.is_file():
        fail("UNIT-ARTIFACT-MANIFEST.json missing")
        continue
    man = json.loads(mpath.read_text(encoding="utf-8"))
    live_sha = sha_norm(out_path)
    R["live_sha256"] = live_sha
    primary_match = False
    for a in man.get("artifacts", []):
        ap = W / a["path"]
        ok = sha_norm(ap) == a.get("sha256") if ap.is_file() else False
        R["sha_rows"].append({"path": a["path"], "role": a.get("role"), "match": ok})
        if Path(a["path"]) == Path(out_rel):
            primary_match = ok
    R["checks"]["manifest_primary_sha_match"] = primary_match
    R["checks"]["supporting_rows_all_match"] = all(r["match"] for r in R["sha_rows"])

    # E live probe re-run (by me, fresh subprocesses)
    pdir = W / f"command-center/p2-wave/probes/{uid}"
    probes = sorted(pdir.glob("probe*.py"))
    for p in probes:
        rel = str(p.relative_to(W))
        try:
            cp = subprocess.run([sys.executable, "-B", rel], cwd=str(W), env=env,
                                capture_output=True, text=True, timeout=600)
            rc, tail = cp.returncode, ((cp.stdout or "") + (cp.stderr or ""))[-240:]
        except Exception as e:
            rc, tail = -999, repr(e)[:240]
        R["probe_results"].append({"probe": p.name, "exit": rc, "tail": tail.strip()[-120:]})
    R["checks"]["probes_exit0"] = (len(probes) >= 2 and all(x["exit"] == 0 for x in R["probe_results"]))

    # F schema, two instruments
    try:
        R["resolver_errors"] = sr.validate_artifact(receipt, ent["output_schema"])
    except Exception as e:
        R["resolver_errors"] = [f"RESOLVER-EXC: {e!r}"]
    derrs = sorted(direct_validator.iter_errors(receipt), key=lambda e: list(map(str, e.absolute_path)))
    R["direct_errors"] = [("/".join(map(str, e.absolute_path)) or "<root>") + ": " + e.message[:200]
                          for e in derrs]
    R["checks"]["schema_resolver_valid"] = (len(R["resolver_errors"]) == 0)
    R["checks"]["schema_direct_valid"] = (len(R["direct_errors"]) == 0)

    # evidence/consistency info (non-verdict): receipt-recorded probe commands vs disk
    for e in receipt.get("evidence", []):
        for pr in e.get("probes", []):
            cmd = pr.get("command") or ""
            if "probe" in cmd and ".py" in cmd:
                script = cmd.split()[-1]
                if not (W / script).is_file():
                    R["warnings"].append(f"receipt cites missing probe script: {script}")

    # G closure rule
    rev = receipt.get("reviewer") or {}
    R["reviewer_verdict"] = rev.get("verdict")
    R["reviewer_independent"] = rev.get("independent")
    R["reviewer_id"] = rev.get("reviewer_id")
    R["checks"]["closure_rule"] = (rev.get("verdict") == "PASS" and rev.get("independent") is True) \
        if R["state"] == "SUCCESS" else True

    bad = [k for k, v in R["checks"].items() if not v]
    if bad:
        R["verdict"] = "FAIL"
        R["fail_reason"] = "failing checks: " + ", ".join(bad)
    else:
        R["verdict"] = "CONFIRM"
    results.append(R)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")

n_ok = 0
for R in results:
    print(f"{R['unit']} | {R.get('verdict')} | state={R.get('state')} | "
          f"probes={[(x['probe'], x['exit']) for x in R.get('probe_results', [])]} | "
          f"resolver_errs={len(R.get('resolver_errors', []))} direct_errs={len(R.get('direct_errors', []))} | "
          f"sha_primary={R['checks'].get('manifest_primary_sha_match')} supp={R['checks'].get('supporting_rows_all_match')} | "
          f"prev_rev_id={R.get('reviewer_id')}")
    if R.get("fail_reason"):
        print("   FAIL:", R["fail_reason"])
    for e in (R.get("resolver_errors") or [])[:3] + (R.get("direct_errors") or [])[:3]:
        print("   schema:", e[:180])
    for w in R.get("warnings", []):
        print("   warn:", w)
    n_ok += (R.get("verdict") == "CONFIRM")
print(f"CONFIRMED {n_ok}/{len(UNITS)}  ->  {OUT}")
print("RUN_AT", datetime.now(timezone.utc).isoformat())
