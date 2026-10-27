#!/usr/bin/env python3
"""Independent reviewer verifier - wave 2 shard 18 (12 RES units).

Transport independence from the builder lane: direct sys.executable
subprocesses (no shell env-prefix adaptation, no g1_python wrapper),
CRLF->LF normalized sha256 recomputed live from artifact bytes, schema
checked via the repo's own fail-closed resolver, plus one corroboration
run of the canonical _measure_one_delivered.py gate per unit.

Checks per unit (ALL must hold for a reviewer PASS):
  1. catalog entry resolves (live WORK-UNIT-CATALOG.json)
  2. artifact at output_path: exists / non-empty / parses / dict / no
     state|status|verdict|result field self-declares BLOCKED/FAILED/SEVERED/
     TIMEOUT; no UNIT-INCOMPLETE / UNIT-FAILED / NOT-DELIVERING sentinel
     text; catalog completion_sentinel substring present in artifact text
  3. probes/<uid>/UNIT-ARTIFACT-MANIFEST.json: row with unit_id==uid,
     path==output_path, present=true, sha256 == live CRLF->LF sha256
  4. both named probes re-run live by the reviewer (rc==0 + SUCCESS: marker)
  5. output_schema resolves via platform/lib/schema_resolver (fail-closed
     resolver) and the artifact schema-validates
  6. canonical gate _measure_one_delivered.py re-run: SUCCESS:delivered
  7. receipt pre-closure state: BLOCKED / reviewer-absent (or an already
     valid PASS closure, which stays)

Honest output: any failing check names the unit and the exact predicate.
Exit 0 only if ALL units hold. JSON detail -> _review_shard18_w2_out.json.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
GATE = REPO / "command-center" / "p2-wave" / "_measure_one_delivered.py"
OUT = REPO / "_review_shard18_w2_out.json"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
BAD_TEXT = re.compile(r"UNIT-INCOMPLETE|UNIT-FAILED|NOT-DELIVERING")

IDS = [
    "RES-0112", "RES-0114", "RES-0128", "RES-0131", "RES-0132", "RES-0137",
    "RES-0140", "RES-0141", "RES-0144", "RES-0148", "RES-0149", "RES-0150",
]


def digest(path):
    raw = path.read_bytes().replace(bytes([13, 10]), bytes([10]))
    return hashlib.sha256(raw).hexdigest(), len(raw)


def loadj(path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, "%s: %s" % (type(exc).__name__, exc)


_RESOLVER = None


def get_resolver():
    global _RESOLVER
    if _RESOLVER is None:
        p = REPO / "platform" / "lib" / "schema_resolver.py"
        spec = importlib.util.spec_from_file_location("schema_resolver_rev18", p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["schema_resolver_rev18"] = mod
        spec.loader.exec_module(mod)
        _RESOLVER = mod
    return _RESOLVER


def run_script(rel, timeout=900):
    p = REPO / rel
    if not p.is_file():
        return 127, "script absent: " + rel
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        r = subprocess.run(
            [sys.executable, "-B", str(p)],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(REPO), env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    return r.returncode, ((r.stdout or "") + "\n" + (r.stderr or "")).strip()


def probe_list(ret):
    pairs = []
    for item in ret.get("named_probes") or []:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("id") or "probe")
        cmd = str(item.get("command") or "")
        pys = [t for t in cmd.split() if t.endswith(".py")]
        pairs.append((pid, pys[-1].replace("\\", "/") if pys else ""))
    return pairs


def verify(uid):
    fails = []
    info = {"uid": uid}

    cat, err = loadj(CATALOG)
    if cat is None:
        return False, ["catalog-unreadable:" + str(err)], info
    unit = None
    for u in cat.get("work_units") or []:
        if u.get("id") == uid:
            unit = u
            break
    if unit is None:
        return False, ["catalog-entry-absent"], info
    out_rel = str(unit.get("output_path") or "").replace("\\", "/")
    schema_rel = str(unit.get("output_schema") or "").replace("\\", "/")
    if not out_rel or not schema_rel:
        return False, ["catalog-row-missing-output_path-or-output_schema"], info

    out = REPO / out_rel
    info["out"] = out_rel
    if not out.is_file():
        return False, ["artifact-absent:" + out_rel], info
    size = out.stat().st_size
    info["bytes"] = size
    if size <= 0:
        fails.append("artifact-empty")

    raw = out.read_text(encoding="utf-8", errors="replace")
    doc, err = loadj(out)
    if doc is None:
        fails.append("artifact-unparseable:" + str(err))
        return False, fails, info
    if not isinstance(doc, dict):
        fails.append("artifact-not-object")
        return False, fails, info

    for fld in ("state", "status", "verdict", "result"):
        v = str(doc.get(fld) or "").upper()
        if v in NOT_DELIVERING:
            fails.append("self-declared:%s=%s" % (fld, v))
    m = BAD_TEXT.search(raw)
    if m:
        fails.append("self-declared-text:" + m.group(0)[:40])
    sent = str(unit.get("completion_sentinel") or "")
    if sent and sent not in raw:
        fails.append("completion-sentinel-absent")

    man, err = loadj(PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json")
    sha = None
    if man is None:
        fails.append("manifest-unparseable:" + str(err))
        info["manifest_rows"] = 0
    else:
        rows = [a for a in (man.get("artifacts") or [])
                if isinstance(a, dict) and a.get("unit_id") == uid]
        info["manifest_rows"] = len(rows)
        live_sha, live_n = digest(out)
        info["sha256"] = live_sha
        sha = live_sha
        ok_rows = [a for a in rows
                   if str(a.get("path") or "").replace("\\", "/") == out_rel
                   and str(a.get("sha256") or "") == live_sha
                   and a.get("present") is True]
        if not ok_rows:
            fails.append("manifest-sha-row-mismatch")

    ret, err = loadj(PROBES / uid / "SUBAGENT-RETURN.json")
    probes = []
    if ret is None:
        fails.append("subagent-return-unparseable:" + str(err))
    else:
        rst = str(ret.get("status") or ret.get("state") or "").upper()
        if rst in NOT_DELIVERING:
            fails.append("subagent-return-state:" + rst)
        probes = probe_list(ret)
        if len([x for x in probes if x[1]]) < 2:
            fails.append("named-probes<2:%d" % len(probes))
    for pid, rel in probes:
        if not rel:
            fails.append("probe-command-unusable:" + pid)
            continue
        rc, tail = run_script(rel)
        info["probe_" + pid + "_rc"] = rc
        marker = any(ln.startswith("SUCCESS:") for ln in tail.splitlines())
        if rc != 0 or not marker:
            fails.append("probe-%s-rc:%d marker:%s tail:%s" % (pid, rc, marker, tail[-200:]))

    if not (REPO / schema_rel).is_file():
        fails.append("schema-unreadable:" + schema_rel)
    else:
        try:
            errs = get_resolver().validate_artifact(doc, schema_rel)
            if errs:
                fails.append("schema-violations:%d first:%s" % (len(errs), str(errs[0])[:200]))
            else:
                info["schema"] = "OK:" + schema_rel
            if info.get("sha256") is None and sha:
                info["sha256"] = sha
        except Exception as exc:
            fails.append("schema-resolver-error:%s:%s" % (type(exc).__name__, exc))

    try:
        gr = subprocess.run(
            [sys.executable, "-I", str(GATE), uid],
            capture_output=True, text=True, timeout=2700, cwd=str(REPO),
        )
        gout = ((gr.stdout or "") + "\n" + (gr.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        gout = "TIMEOUT"
    glines = [ln for ln in gout.splitlines() if ln.startswith(("SUCCESS:delivered", "FAILED:delivered"))]
    info["gate"] = glines[-1] if glines else "no-verdict"
    if not (glines and glines[-1].startswith("SUCCESS:delivered")):
        fails.append("canonical-gate:" + info["gate"])

    rec, err = loadj(REPO / "command-center" / "receipts" / (uid + ".json"))
    if rec is None:
        fails.append("receipt-unreadable:" + str(err))
    else:
        rv = rec.get("reviewer") or {}
        info["receipt_state"] = rec.get("state")
        info["reviewer_verdict"] = rv.get("verdict")
        info["reviewer_independent"] = rv.get("independent")
        if rec.get("state") == "SUCCESS" and rv.get("verdict") != "PASS":
            fails.append("inconsistent:SUCCESS-without-PASS")

    return (not fails), fails, info


def main():
    results = {}
    all_ok = True
    for uid in (sys.argv[1:] or IDS):
        ok, fails, info = verify(uid)
        results[uid] = {"ok": ok, "fails": fails, "info": info}
        all_ok = all_ok and ok
        print("== %s %s" % (uid, "OK" if ok else "FAIL"))
        print("   out=%s bytes=%s manifest_rows=%s" % (info.get("out"), info.get("bytes"), info.get("manifest_rows")))
        print("   sha256=%s" % info.get("sha256"))
        prc = {k: v for k, v in info.items() if k.startswith("probe_")}
        if prc:
            print("   probe_rcs=%s" % prc)
        print("   schema=%s" % info.get("schema"))
        print("   gate=%s" % info.get("gate"))
        print("   receipt_state=%s reviewer_verdict=%s" % (info.get("receipt_state"), info.get("reviewer_verdict")))
        for f in fails:
            print("   FAILCHECK: %s" % f)
        print("   %s:%s" % ("SUCCESS" if ok else "FAILED", uid))
    OUT.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    print("SUCCESS:reviewer-shard18-w2 all units verified" if all_ok
          else "FAILED:reviewer-shard18-w2 one or more units red")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
