#!/usr/bin/env python3
"""Independent reviewer battery -- wave 4 shard 18 (12 units, TST-0092..TST-0138).

Adversarially verifies per unit:
  A. artifact exists / non-empty / parses / not self-BLOCKED-FAILED
  B. completion_sentinel present
  C. live probes re-run by THIS reviewer (exit 0 each)
  D. sha256(CRLF->LF artifact) matches UNIT-ARTIFACT-MANIFEST.json row
  E. output_schema validation (jsonschema, $defs pointer resolved)
  F. receipt_core invariant: state=SUCCESS => reviewer PASS + independent
NO receipt is modified here; this battery only gathers verdicts.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
UNITS = ["TST-0092", "TST-0094", "TST-0100", "TST-0109", "TST-0113", "TST-0116",
         "TST-0124", "TST-0129", "TST-0130", "TST-0136", "TST-0137", "TST-0138"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT = 180  # seconds per probe

import jsonschema


def norm_digest(p):
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_schema(ref):
    filepart, _, frag = ref.partition("#")
    schema_path = REPO / filepart
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if frag:
        node = schema
        for part in [x for x in frag.split("/") if x]:
            node = node[part.replace("~1", "/").replace("~0", "~")]
        resolver = jsonschema.RefResolver(
            base_uri=schema_path.resolve().as_uri(), referrer=schema)
        return node, resolver
    return schema, jsonschema.RefResolver(
        base_uri=schema_path.resolve().as_uri(), referrer=schema)


def main():
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    cmap = {u["id"]: u for u in cat["work_units"] if isinstance(u, dict) and "id" in u}
    results = {}
    overall_fail = False
    env = {k: os.environ.get(k, "") for k in
           ("PATH", "SYSTEMROOT", "COMSPEC", "TEMP", "TMP", "USERPROFILE")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for uid in UNITS:
        unit = cmap[uid]
        checks = {}
        out = REPO / unit["output_path"]
        doc = None
        try:
            text = out.read_text(encoding="utf-8")
            doc = json.loads(text)
            checks["parse"] = True
            checks["nonempty"] = out.stat().st_size > 0
            st = str(doc.get("state", "")).upper()
            checks["not-self-blocked"] = (st not in NOT_DELIVERING) and st != ""
            checks["sentinel"] = unit["completion_sentinel"] in text
            state = st
        except Exception as exc:
            checks["parse"] = False
            checks["nonempty"] = out.exists() and out.stat().st_size > 0
            checks["not-self-blocked"] = False
            checks["sentinel"] = False
            state = "UNREADABLE:%s" % type(exc).__name__
        rev = (doc.get("reviewer") or {}) if isinstance(doc, dict) else {}
        checks["core-success-needs-pass"] = True
        if state == "SUCCESS":
            checks["core-success-needs-pass"] = (
                str(rev.get("verdict", "")).upper() == "PASS"
                and rev.get("independent") is True)
        probe_results = []
        for probe in sorted((REPO / "command-center/p2-wave/probes" / uid).glob("probe*.py")):
            try:
                cp = subprocess.run(
                    [sys.executable, "-B", str(probe)],
                    cwd=str(REPO), capture_output=True, text=True,
                    timeout=PROBE_TIMEOUT, env=env)
                probe_results.append((probe.name, cp.returncode,
                                      (cp.stdout or cp.stderr).strip()[:260]))
            except subprocess.TimeoutExpired:
                probe_results.append((probe.name, "TIMEOUT", ""))
        checks["probes-exit0"] = bool(probe_results) and all(r[1] == 0 for r in probe_results)
        try:
            man = json.loads((REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
            live_sha, nbytes = norm_digest(out)
            rows = [a for a in man.get("artifacts", [])
                    if isinstance(a, dict) and a.get("unit_id") == uid
                    and str(a.get("path", "")).replace("\\", "/") == unit["output_path"]
                    and a.get("present") is True]
            checks["manifest-sha"] = any(a.get("sha256") == live_sha for a in rows)
            sha_detail = live_sha[:12]
        except Exception as exc:
            checks["manifest-sha"] = False
            sha_detail = type(exc).__name__
        try:
            schema, resolver = load_schema(unit["output_schema"])
            jsonschema.Draft7Validator(schema, resolver=resolver).validate(doc)
            checks["schema"] = True
        except Exception as exc:
            checks["schema"] = "FAIL: %s: %s" % (type(exc).__name__, str(exc)[:300])
        ok = all(v is True for v in checks.values())
        if not ok:
            overall_fail = True
        results[uid] = {"ok": ok, "state": state, "checks": checks,
                        "probes": [[n, r, s] for n, r, s in probe_results],
                        "live_sha12": sha_detail,
                        "reviewer": {"verdict": rev.get("verdict"),
                                     "independent": rev.get("independent")}}
        print(("OK  " if ok else "FAIL"), uid, "state=" + str(state))
        for k, v in checks.items():
            if v is not True:
                print("     -", k, "=>", v)
        for name, rc, snip in probe_results:
            if rc != 0:
                print("     probe", name, "rc=%s" % rc, snip)
    (Path(__file__).parent / "battery-results.json").write_text(
        json.dumps(results, indent=1), encoding="utf-8")
    print("BATTERY:", "ANY-FAIL" if overall_fail else "ALL-OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
