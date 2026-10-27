#!/usr/bin/env python3
"""Independent reviewer verifier - wave 3 shard 17 (12 RES units).

Units: RES-0114, 0128, 0144, 0151, 0157, 0158, 0160, 0162, 0164, 0168,
0175, 0176.  This reviewer did not build these units; the review closes them.

Checks per unit (ALL must hold for a reviewer PASS):
  1. catalog entry resolves (live WORK-UNIT-CATALOG.json)
  2. artifact at output_path: exists / non-empty / parses / dict / no
     state|status|verdict|result field self-declares BLOCKED/FAILED/SEVERED/
     TIMEOUT; no UNIT-INCOMPLETE / UNIT-FAILED / NOT-DELIVERING text;
     catalog completion_sentinel substring present in artifact text
  3. probes/<uid>/UNIT-ARTIFACT-MANIFEST.json: row with unit_id==uid,
     path==output_path, present=true, sha256 == live CRLF->LF sha256
  4. every named command probe re-run live by the reviewer (rc==0 +
     SUCCESS: marker); .py via sys.executable -B, .mjs via node,
     env prefixes moved into the child env (Windows-safe)
  5. output_schema validates via platform/lib/schema_resolver (fail-closed)
  6. canonical gate _measure_one_delivered.py re-run: SUCCESS:delivered
  7. receipt pre-closure state: BLOCKED / reviewer-absent

Honest output: any failing check names the unit and the exact predicate.
Exit 0 only if ALL units hold. JSON detail -> _review_w3s17_out.json.
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
OUT = REPO / "_review_w3s17_out.json"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
BAD_TEXT = re.compile(r"UNIT-INCOMPLETE|UNIT-FAILED|NOT-DELIVERING")

IDS = [
    "RES-0114", "RES-0128", "RES-0144", "RES-0151", "RES-0157", "RES-0158",
    "RES-0160", "RES-0162", "RES-0164", "RES-0168", "RES-0175", "RES-0176",
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
        spec = importlib.util.spec_from_file_location("schema_resolver_w3s17", p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["schema_resolver_w3s17"] = mod
        spec.loader.exec_module(mod)
        _RESOLVER = mod
    return _RESOLVER


def probe_script(cmd):
    """Return (kind, script_rel) or (None, None); env prefixes stripped."""
    toks = cmd.split()
    while toks and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=\S+$", toks[0]):
        toks = toks[1:]
    if not toks:
        return None, None
    exe = toks[0]
    scripts = [t.replace("\\", "/") for t in toks
               if t.endswith((".py", ".mjs"))]
    if not scripts:
        return None, None
    if exe.startswith("python"):
        return "py", scripts[-1]
    if exe == "node":
        return "node", scripts[-1]
    return None, None


def run_probe(kind, rel, timeout=900):
    p = REPO / rel
    if not p.is_file():
        return 127, "script absent: " + rel
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    argv = [sys.executable, "-B", str(p)] if kind == "py" else ["node", str(p)]
    try:
        r = subprocess.run(argv, capture_output=True, text=True,
                           timeout=timeout, cwd=str(REPO), env=env)
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    return r.returncode, ((r.stdout or "") + "\n" + (r.stderr or "")).strip()


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
    if man is None:
        fails.append("manifest-unparseable:" + str(err))
        info["manifest_rows"] = 0
    else:
        rows = [a for a in (man.get("artifacts") or [])
                if isinstance(a, dict) and a.get("unit_id") == uid]
        info["manifest_rows"] = len(rows)
        live_sha, live_n = digest(out)
        info["sha256"] = live_sha
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
        for item in ret.get("named_probes") or []:
            if not isinstance(item, dict):
                continue
            pid = str(item.get("id") or "probe")
            cmd = str(item.get("command") or "")
            kind, rel = probe_script(cmd)
            probes.append((pid, kind, rel, cmd))
        if len([x for x in probes if x[2]]) < 2:
            fails.append("named-probes<2:%d" % len([x for x in probes if x[2]]))
    for pid, kind, rel, cmd in probes:
        if not rel:
            fails.append("probe-command-unusable:%s:%s" % (pid, cmd[:80]))
            continue
        rc, tail = run_probe(kind, rel)
        info["probe_" + pid + "_rc"] = rc
        marker = any(ln.startswith("SUCCESS:") for ln in tail.splitlines())
        if rc != 0 or not marker:
            fails.append("probe-%s-rc:%d marker:%s tail:%s"
                         % (pid, rc, marker, tail[-200:]))

    if not (REPO / schema_rel).is_file():
        fails.append("schema-unreadable:" + schema_rel)
    else:
        try:
            errs = get_resolver().validate_artifact(doc, schema_rel)
            if errs:
                fails.append("schema-violations:%d first:%s"
                             % (len(errs), str(errs[0])[:200]))
            else:
                info["schema"] = "OK:" + schema_rel
        except Exception as exc:
            fails.append("schema-resolver-error:%s:%s"
                         % (type(exc).__name__, exc))

    try:
        gr = subprocess.run(
            [sys.executable, "-I", str(GATE), uid],
            capture_output=True, text=True, timeout=2700, cwd=str(REPO),
        )
        gout = ((gr.stdout or "") + "\n" + (gr.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        gout = "TIMEOUT"
    glines = [ln for ln in gout.splitlines()
              if ln.startswith(("SUCCESS:delivered", "FAILED:delivered"))]
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
        if rec.get("state") == "SUCCESS":
            if not (rv.get("verdict") == "PASS" and rv.get("independent") is True):
                fails.append("receipt-self-success-without-independent-pass")
        elif rec.get("state") == "BLOCKED":
            cls = (rec.get("failure") or {}).get("classification") or []
            if rv.get("verdict") == "PASS" and rv.get("independent") is True:
                pass  # already-valid closure; stays SUCCESS-shaped
            elif "reviewer-absent" not in [str(c) for c in cls]:
                fails.append("receipt-blocked-not-reviewer-absent")
        else:
            fails.append("receipt-unexpected-state:%s" % rec.get("state"))

    return (not fails), fails, info


def main() -> int:
    results = {}
    all_ok = True
    for uid in IDS:
        ok, fails, info = verify(uid)
        results[uid] = {"ok": ok, "fails": fails, "info": info}
        tag = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
        print("%s %s %s" % (tag, uid, "; ".join(fails[:3]) if fails else "all-checks-hold"))
    OUT.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    print("detail -> %s" % OUT)
    print("SUCCESS:w3s17-reviewer-verify" if all_ok else "FAILED:w3s17-reviewer-verify")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
