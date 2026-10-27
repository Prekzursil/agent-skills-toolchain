#!/usr/bin/env python3
"""shard15-w3 INDEPENDENT REVIEWER read-only battery.

Per unit, all checks re-derived from scratch by THIS reviewer (no builder output trusted):
  A catalog entry
  B artifact: exists / non-empty / parses / not self-declared BLOCKED-FAILED-SEVERED-TIMEOUT /
    catalog completion_sentinel present in artifact text
  C live probes re-run by the reviewer (probe*.py directly), exit 0 required
  D per-unit UNIT-ARTIFACT-MANIFEST.json sha256 row (CRLF->LF) matches live artifact bytes
  E strict output_schema validation (receipt_core, kind-pinned when the catalog declares a class)
  F receipt_core SUCCESS predicate on the receipt (incl. reviewer PASS+independent)
  G canonical delivery measure (_measure_one_delivered.py) in a fresh process
READ-ONLY: writes nothing inside command-center/. Results -> battery-results.json.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from jsonschema import Draft202012Validator

REPO = Path.home() / "p2-g1"
IDS = ["IMP-0478", "REL-0001", "REL-0006", "REL-0014", "REL-0017", "REL-0020",
       "REL-0021", "REL-0022", "RES-0004", "RES-0009", "RES-0011", "RES-0020"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

# ---- schemas (LOCAL platform schemas only; absolute file:// refs are NOT followed) ----
full = json.loads((REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8"))
DEFS = full.get("$defs", {})
CORE_VAL = Draft202012Validator({
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "allOf": [{"$ref": "#/$defs/receipt_core"}],
    "$defs": DEFS,
})
profiles = json.loads((REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(encoding="utf-8"))
PDEFS = profiles.get("$defs", {})


def kind_val(cls):
    return Draft202012Validator({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "allOf": [{"$ref": "#/$defs/%s" % cls}],
        "$defs": {**DEFS, **PDEFS},
    })


def norm_digest(path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def jload(p):
    try:
        return json.loads(p.read_text(encoding="utf-8")), None
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


def probe_env():
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    hook_dir = str(REPO / "command-center/p2-wave/seed-stage")
    env["PYTHONPATH"] = os.pathsep.join([hook_dir, str(REPO), str(REPO / "tools"),
                                         str(REPO / "tools/measure-guard"), str(REPO / "platform/lib"),
                                         str(REPO / "tools/agentspec"), env.get("PYTHONPATH", "")])
    return env


def run(cmd, timeout=2700):
    # Windows cmd.exe cannot execute POSIX "VAR=value command" prefixes
    # (shard11 gotcha). Move them into the child env.
    import re as _re
    while True:
        m = _re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            break
        cmd = cmd[m.end():]
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                       text=True, timeout=timeout, env=probe_env())
    tail = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, tail[-2000:]


results = {}
for uid in IDS:
    r = {"unit": uid, "checks": {}}
    cat, _ = jload(REPO / "command-center/WORK-UNIT-CATALOG.json")
    entry = next((u for u in cat.get("work_units", []) if isinstance(u, dict) and u.get("id") == uid), None)
    r["checks"]["catalog"] = "PASS" if entry else "FAIL:catalog-missing"
    out_rel = str((entry or {}).get("output_path") or "")
    out = REPO / out_rel if out_rel else None
    declared_schema = str((entry or {}).get("output_schema") or "")
    sent = str((entry or {}).get("completion_sentinel") or "")

    # B artifact
    doc = None
    if out and out.is_file() and out.stat().st_size > 0:
        doc, perr = jload(out)
        if doc is None:
            r["checks"]["artifact"] = "FAIL:unparseable:%s" % perr
        else:
            st = str(doc.get("state") or "").upper() if isinstance(doc, dict) else ""
            if st in NOT_DELIVERING:
                r["checks"]["artifact"] = "FAIL:self-declared:%s" % st
            else:
                txt = out.read_text(encoding="utf-8")
                r["checks"]["artifact"] = "PASS" if (not sent or sent in txt) else "FAIL:sentinel-absent"
    else:
        r["checks"]["artifact"] = "FAIL:absent-or-empty"

    # C probes: reviewer re-runs every probeN*.py script directly
    pdir = REPO / "command-center/p2-wave/probes" / uid
    probes = sorted(pdir.glob("probe*.py"))
    pres = {}
    for p in probes:
        cmd = 'PYTHONDONTWRITEBYTECODE=1 "%s" -B %s' % (sys.executable, p.relative_to(REPO).as_posix())
        t0 = time.time()
        try:
            rc, tail = run(cmd)
        except subprocess.TimeoutExpired:
            rc, tail = 124, "TIMEOUT"
        pres[p.name] = {"rc": rc, "secs": round(time.time() - t0, 1), "tail": tail[-400:]}
    r["probes"] = pres
    if pres and all(v["rc"] == 0 for v in pres.values()):
        r["checks"]["probes"] = "PASS"
    else:
        bad = ",".join("%s=rc%s" % (k, v["rc"]) for k, v in pres.items() if v["rc"] != 0)
        r["checks"]["probes"] = "FAIL:" + (bad or "no-probes-found")

    # D manifest sha
    man, _ = jload(pdir / "UNIT-ARTIFACT-MANIFEST.json")
    sha, nbytes = norm_digest(out)
    rows = [a for a in (man or {}).get("artifacts", []) if isinstance(a, dict) and a.get("unit_id") == uid]
    ok = any(str(a.get("path") or "").replace("\\", "/") == out_rel
             and str(a.get("sha256") or "") == sha
             and a.get("present") is True for a in rows)
    r["manifest_live_sha"] = sha
    r["manifest_live_bytes"] = nbytes
    r["manifest_rows"] = rows
    r["checks"]["manifest_sha"] = "PASS" if ok else "FAIL:manifest-sha-mismatch"

    # E strict output_schema (kind-pinned when declared class exists)
    if doc is not None:
        errs = sorted(CORE_VAL.iter_errors(doc), key=lambda e: [str(x) for x in e.path])
        base = [{"path": "/".join(str(x) for x in e.path) or "<root>", "msg": e.message[:260]} for e in errs]
        r["schema_core_errors"] = base
        cls = declared_schema.rsplit("/", 1)[-1].replace(".schema.json", "")
        kerrs = None
        if cls in PDEFS:
            kerrs = []
            for e in sorted(kind_val(cls).iter_errors(doc), key=lambda e: [str(x) for x in e.path]):
                kerrs.append({"path": "/".join(str(x) for x in e.path) or "<root>", "msg": e.message[:260]})
        r["declared_kind"] = cls if cls in PDEFS else None
        r["schema_kind_errors"] = kerrs
        total = len(errs) + (len(kerrs) if kerrs else 0)
        r["checks"]["output_schema"] = "PASS" if total == 0 else "FAIL:schema-invalid(%d)" % total
    else:
        r["checks"]["output_schema"] = "FAIL:artifact-unparsed"

    # F receipt_core SUCCESS predicate
    if isinstance(doc, dict):
        rev = doc.get("reviewer") or {}
        state = doc.get("state")
        pred = {
            "state": state,
            "reviewer_verdict": rev.get("verdict"),
            "reviewer_independent": rev.get("independent"),
            "success_implies_open_p0p1": any(
                d.get("severity") in ("P0", "P1") and d.get("status") == "open"
                for d in doc.get("defects", []) if isinstance(d, dict)),
            "sentinel_failed_prefix": str(doc.get("sentinel", "")).startswith("FAILED:"),
        }
        r["success_predicate"] = pred
        if state == "SUCCESS":
            good = (rev.get("verdict") == "PASS" and rev.get("independent") is True
                    and not pred["success_implies_open_p0p1"] and not pred["sentinel_failed_prefix"])
            r["checks"]["success_predicate"] = "PASS" if good else "FAIL:success-without-valid-independent-closure"
        else:
            r["checks"]["success_predicate"] = "PASS(state-not-success)"

    # G canonical measure, fresh process
    t0 = time.time()
    mrc, mtail = run('PYTHONDONTWRITEBYTECODE=1 "%s" -B command-center/p2-wave/_measure_one_delivered.py %s'
                     % (sys.executable, uid))
    r["measure"] = {"rc": mrc, "secs": round(time.time() - t0, 1),
                    "verdict": (mtail.strip().splitlines()[-1][:200] if mtail.strip() else "")}
    results[uid] = r
    greens = [k for k, v in r["checks"].items() if str(v).startswith("PASS")]
    reds = [k for k, v in r["checks"].items() if not str(v).startswith("PASS")]
    print("%s: GREEN=%s RED=%s" % (uid, greens, reds), flush=True)

out_path = REPO / "_p2shard15-w3-review/battery-results.json"
out_path.write_text(json.dumps(results, indent=1), encoding="utf-8")
print("WROTE %s" % out_path, flush=True)
