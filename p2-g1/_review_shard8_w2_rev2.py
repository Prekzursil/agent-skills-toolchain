#!/usr/bin/env python3
"""Independent reviewer battery, wave 2 shard 8 rev2 (12 CNF units).

Fresh independent verification - NOT derived from _review_shard8_w2_battery.py.
Per unit:
  1. catalog entry exists (WORK-UNIT-CATALOG.json work_units)
  2. artifact at catalog output_path: exists, non-empty, parses, not self-BLOCKED/FAILED,
     catalog completion sentinel text present, receipt min_bytes_threshold met
  3. live probes re-run HERE: every probes/<id>/probe*.py, exit 0 AND all_ok=true
  4. probes/<id>/UNIT-ARTIFACT-MANIFEST.json: primary row sha256 (CRLF->LF) matches the
     live artifact; every manifest row re-hashed
  5. output_schema validated by the estate validator (platform/lib/schema_resolver.py)
     plus an independent raw Draft7 cross-check
  6. receipt_core: receipt state=SUCCESS requires reviewer.verdict=PASS + independent=true
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
OUT = REPO / "_review_shard8_w2_rev2_out.json"
IDS = ["CNF-0077", "CNF-0089", "CNF-0129", "CNF-0142", "CNF-0147", "CNF-0149",
       "CNF-0152", "CNF-0153", "CNF-0158", "CNF-0163", "CNF-0166", "CNF-0167"]


def sha_lf(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def load_resolver():
    spec = importlib.util.spec_from_file_location(
        "schema_resolver_rev2", REPO / "platform" / "lib" / "schema_resolver.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["schema_resolver_rev2"] = mod
    spec.loader.exec_module(mod)
    return mod


def run_probe(uid: str, fname: str):
    cmd = [sys.executable, "-B", "command-center/p2-wave/probes/" + uid + "/" + fname]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True,
                       timeout=300, env=env)
    out = ((p.stdout or "") + "\n" + (p.stderr or "")).strip()
    all_ok = None
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                j = json.loads(line)
                if "all_ok" in j:
                    all_ok = j.get("all_ok")
                    break
            except Exception:
                pass
    return p.returncode, all_ok, out[-600:]


def raw_jsonschema_check(doc, schema_rel: str):
    """Independent second signal: raw Draft7 with file-URI ref resolution."""
    import jsonschema
    sp = REPO / schema_rel
    schema = json.loads(sp.read_text(encoding="utf-8"))
    errs = []
    resolver = jsonschema.RefResolver(base_uri=sp.as_uri(), referrer=schema)
    for e in jsonschema.Draft7Validator(schema, resolver=resolver).iter_errors(doc):
        loc = "/".join(str(p) for p in e.absolute_path)
        errs.append(loc + ": " + e.message[:200])
    return errs


def review(uid: str, cat_by_id: dict, resolver) -> dict:
    ent = cat_by_id.get(uid)
    R: dict = {"unit": uid}
    if not ent:
        R["fatal"] = ["no-catalog-entry"]
        R["VERDICT"] = "FAIL"
        return R
    out_rel = ent.get("output_path")
    sch_rel = ent.get("output_schema")
    R["output_path"] = out_rel
    R["output_schema"] = sch_rel
    fatal: list = []

    art_p = REPO / out_rel
    if not art_p.is_file():
        R["artifact-exists"] = False
        fatal.append("artifact-missing-at-catalog-output_path")
    else:
        R["artifact-exists"] = True
        raw = art_p.read_bytes()
        R["artifact-bytes"] = len(raw)
        if len(raw) == 0:
            fatal.append("artifact-empty")
        doc = None
        try:
            doc = json.loads(raw.decode("utf-8"))
            R["artifact-parses"] = True
        except Exception as exc:
            R["artifact-parses"] = False
            fatal.append("artifact-unparseable:%s" % type(exc).__name__)
        if isinstance(doc, dict):
            st = doc.get("state")
            R["artifact-state-field"] = st
            if isinstance(st, str) and st.upper() in ("BLOCKED", "FAILED"):
                fatal.append("artifact-self-declared-%s" % st.upper())
        marker = "SUCCESS:" + uid
        text = raw.decode("utf-8", errors="replace")
        R["sentinel-marker-in-artifact"] = marker in text
        if marker not in text:
            fatal.append("completion-sentinel-SUCCESS-marker-absent")

        rp = REPO / "command-center" / "receipts" / (uid + ".json")
        rec = {}
        if rp.is_file():
            rec = json.loads(rp.read_text(encoding="utf-8"))
        else:
            fatal.append("receipt-missing")
        R["receipt-state"] = rec.get("state")
        rv = rec.get("reviewer") or {}
        R["receipt-reviewer-verdict"] = rv.get("verdict")
        R["receipt-reviewer-independent"] = rv.get("independent")
        if rec.get("state") == "SUCCESS":
            if rv.get("verdict") != "PASS" or rv.get("independent") is not True:
                fatal.append("receipt-core-violation:SUCCESS-without-verified-independent-PASS")
        thr = rec.get("min_bytes_threshold")
        if isinstance(thr, int) and len(raw) < thr:
            fatal.append("below-min-bytes:%d<%d" % (len(raw), thr))

        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        probes = sorted(x.name for x in pdir.glob("probe*.py")) if pdir.is_dir() else []
        R["probes-run"] = {}
        for fname in probes:
            try:
                rc, all_ok, tail = run_probe(uid, fname)
            except subprocess.TimeoutExpired:
                rc, all_ok, tail = -1, None, "TIMEOUT>300s"
            R["probes-run"][fname] = {"rc": rc, "all_ok": all_ok}
            if rc != 0:
                fatal.append("probe-%s-exit%d" % (fname, rc))
            elif all_ok is not True:
                fatal.append("probe-%s-all_ok=%r" % (fname, all_ok))
        if not probes:
            fatal.append("no-probe-scripts-found")

        man_p = pdir / "UNIT-ARTIFACT-MANIFEST.json"
        if not man_p.is_file():
            R["manifest-file-exists"] = False
            fatal.append("UNIT-ARTIFACT-MANIFEST-missing")
        else:
            R["manifest-file-exists"] = True
            man = json.loads(man_p.read_text(encoding="utf-8"))
            rows = man.get("artifacts") or []
            prim = [r for r in rows if r.get("role") == "primary" and r.get("path") == out_rel]
            R["manifest-primary-row-present"] = bool(prim)
            live_sha = sha_lf(raw)
            R["live-sha256-lf"] = live_sha
            if prim:
                R["manifest-primary-sha"] = prim[0].get("sha256")
                if prim[0].get("sha256") != live_sha:
                    fatal.append("manifest-primary-sha-mismatch live=%s manifest=%s"
                                 % (live_sha[:16], str(prim[0].get("sha256"))[:16]))
                if isinstance(prim[0].get("bytes"), int) and prim[0]["bytes"] != len(raw):
                    fatal.append("manifest-primary-bytes-mismatch live=%d manifest=%d"
                                 % (len(raw), prim[0]["bytes"]))
            else:
                fatal.append("manifest-has-no-primary-row-for-output_path")
            mism = []
            for r in rows:
                p2 = REPO / str(r.get("path", "_"))
                if not p2.is_file():
                    mism.append(str(r.get("path")) + ":absent")
                    continue
                b = p2.read_bytes()
                if sha_lf(b) != r.get("sha256"):
                    mism.append(str(r.get("path")) + ":sha-mismatch")
            R["manifest-all-rows-mismatch"] = mism
            if mism:
                fatal.append("manifest-rows-rehash-mismatch:" + ";".join(mism[:4]))

        try:
            errs = resolver.validate_artifact(doc, sch_rel)
        except Exception as exc:
            errs = ["resolver-crash:%s:%s" % (type(exc).__name__, str(exc)[:200])]
        R["schema-resolver-errors"] = errs
        if errs:
            fatal.append("output-schema-invalid:%d-errors first=%s" % (len(errs), errs[0][:200]))
        try:
            errs7 = raw_jsonschema_check(doc, sch_rel)
        except Exception as exc:
            errs7 = ["raw-crash:%s" % type(exc).__name__]
        R["schema-raw-draft7-error-count"] = len(errs7)
        R["schema-raw-draft7-first"] = errs7[0][:220] if errs7 else None
        if errs7 and not errs:
            fatal.append("raw-draft7-only-errors:%d first=%s" % (len(errs7), errs7[0][:200]))

    R["fatal"] = fatal
    R["VERDICT"] = "FAIL" if fatal else "PASS"
    return R


def main() -> int:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    by_id = {u.get("id"): u for u in cat["work_units"]}
    resolver = load_resolver()
    out = {}
    for uid in IDS:
        t0 = time.time()
        R = review(uid, by_id, resolver)
        R["seconds"] = round(time.time() - t0, 1)
        out[uid] = R
        print("%-9s %s %s" % (uid, R["VERDICT"], (R.get("fatal") or ["clean"])[:2]), flush=True)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    bad = [u for u, r in out.items() if r.get("VERDICT") != "PASS"]
    print("PASS:%d FAIL:%d %s" % (len(out) - len(bad), len(bad), bad))
    print("SUCCESS:review-shard8-w2-rev2" if not bad else "FAILED:review-shard8-w2-rev2 units=%s" % ",".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
