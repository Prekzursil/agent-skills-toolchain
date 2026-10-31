#!/usr/bin/env python3
"""Independent reviewer battery - wave 2 BUILD shard 14 (12 IMP units).

Unit-list derivation (evidence, not guesswork): the engine forms review
shards from build shards; sibling reviewers review:w2s13 and review:w2s15
closed exactly the build:w2s13 / build:w2s15 reported unit lists. The
journaled build:w2s14 BUILD_SCHEMA_WAVE result lists these 12 ids as
built-awaiting-review. Receipts already carry PASS closures (carried
forward by the build lane per the keep-existing-closure rule); this
reviewer independently re-verifies every predicate and CONFIRMS or
FAILS each closure.

Checks per unit (ALL must hold to confirm the PASS closure):
  1. catalog entry live: output_path + output_schema present
  2. artifact at output_path: exists / non-empty / parses / dict
  3. not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT (state field) and no
     UNIT-INCOMPLETE|UNIT-FAILED|NOT-DELIVERING text in bytes
  4. catalog completion_sentinel present in artifact text
  5. receipt_core: state=SUCCESS requires reviewer.verdict=PASS AND
     reviewer.independent=true; no contradictory failure block
  6. probes/<uid>/UNIT-ARTIFACT-MANIFEST.json: row unit_id==uid,
     path==output_path, present=true, sha256 == live CRLF->LF sha256
  7. SUBAGENT-RETURN.json: status/state not NOT-DELIVERING; >=2 named
     probes; BOTH re-run live by this reviewer (direct sys.executable
     argv subprocesses - transport independent of builder lane and gate
     wrapper): rc==0 AND a SUCCESS: marker on stdout/stderr
  8. output_schema: fail-closed platform/lib/schema_resolver validation of
     the live artifact (full decorated catalog declaration)
  9. canonical gate _measure_one_delivered.py re-run: SUCCESS:delivered
  + informational: receipt artifacts[] sha256 rows vs live files (report only)

Any failing check -> FAIL verdict recorded in results.json; receipts are
NOT modified by this battery (closure confirmation only).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
os.environ.setdefault("AST_INTEGRATE_ROOT", str(REPO))
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
GATE = REPO / "command-center" / "p2-wave" / "_measure_one_delivered.py"
RESOLVER = REPO / "platform" / "lib" / "schema_resolver.py"
OUT = REPO / "_rev-w2-shard14" / "results.json"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
BAD_TEXT = re.compile(r"UNIT-INCOMPLETE|UNIT-FAILED|NOT-DELIVERING")

IDS = [
    "IMP-0304", "IMP-0306", "IMP-0321", "IMP-0329", "IMP-0355", "IMP-0360",
    "IMP-0374", "IMP-0390", "IMP-0402", "IMP-0409", "IMP-0415", "IMP-0421",
]


def digest(path: Path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def loadj(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, "%s: %s" % (type(exc).__name__, exc)


def run_probe(rel: str, timeout: int = 900):
    """Independent transport: direct argv subprocess, no shell, no wrapper."""
    p = REPO / rel
    if not p.is_file():
        return 127, "script absent: " + rel
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        r = subprocess.run([sys.executable, "-B", str(p)],
                           capture_output=True, text=True, timeout=timeout,
                           cwd=str(REPO), env=env)
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT after %ds" % timeout
    return r.returncode, ((r.stdout or "") + "\n" + (r.stderr or "")).strip()


def probe_pairs(ret):
    pairs = []
    for item in ret.get("named_probes") or []:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("id") or "probe")
        cmd = str(item.get("command") or "")
        pys = [t for t in cmd.split() if t.endswith(".py")]
        pairs.append((pid, cmd, pys[-1].replace("\\", "/") if pys else ""))
    return pairs


def verify(uid: str):
    fails, notes, info = [], [], {"uid": uid}

    cat, err = loadj(CATALOG)
    if cat is None:
        return False, ["catalog-unreadable:" + str(err)], info
    unit = next((u for u in cat.get("work_units") or [] if u.get("id") == uid), None)
    if unit is None:
        return False, ["catalog-entry-absent"], info
    out_rel = str(unit.get("output_path") or "").replace("\\", "/")
    schema_decl = str(unit.get("output_schema") or "")
    if not out_rel or not schema_decl:
        return False, ["catalog-row-missing-output_path-or-output_schema"], info
    info["out"] = out_rel
    info["schema_decl"] = schema_decl

    # (2)(3)(4) artifact = the receipt itself
    out = REPO / out_rel
    if not out.is_file():
        return False, ["artifact-absent:" + out_rel], info
    size = out.stat().st_size
    info["bytes"] = size
    if size <= 0:
        fails.append("artifact-empty")
    doc, err = loadj(out)
    if doc is None:
        fails.append("artifact-unparseable:" + str(err))
        return False, fails, info
    if not isinstance(doc, dict):
        fails.append("artifact-not-object")
        return False, fails, info
    raw = out.read_text(encoding="utf-8", errors="replace")
    st = str(doc.get("state") or "").upper()
    info["receipt_state"] = doc.get("state")
    if st in NOT_DELIVERING:
        fails.append("self-declared:state=%s" % st)
    m = BAD_TEXT.search(raw)
    if m:
        fails.append("self-declared-text:" + m.group(0)[:40])
    sent = str(unit.get("completion_sentinel") or "")
    if sent and sent not in raw:
        fails.append("completion-sentinel-absent:" + sent[:60])

    # (5) receipt_core consistency
    rv = doc.get("reviewer") or {}
    info["reviewer_verdict"] = rv.get("verdict")
    info["reviewer_independent"] = rv.get("independent")
    if doc.get("state") == "SUCCESS":
        if rv.get("verdict") != "PASS" or rv.get("independent") is not True:
            fails.append("receipt-core:SUCCESS-without-PASS+independent")
        if doc.get("failure"):
            fails.append("receipt-core:SUCCESS-with-failure-block")

    # (6) manifest sha row
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

    # (7) subagent return + LIVE probe reruns (reviewer transport)
    ret, err = loadj(PROBES / uid / "SUBAGENT-RETURN.json")
    if ret is None:
        fails.append("subagent-return-unparseable:" + str(err))
        pairs = []
    else:
        rst = str(ret.get("status") or ret.get("state") or "").upper()
        if rst in NOT_DELIVERING:
            fails.append("subagent-return-state:" + rst)
        pairs = probe_pairs(ret)
        if len([x for x in pairs if x[2]]) < 2:
            fails.append("named-probes<2:%d" % len(pairs))
    for pid, cmd, rel in pairs:
        if not rel:
            fails.append("probe-command-unusable:" + pid)
            continue
        rc, tail = run_probe(rel)
        info["probe_" + pid + "_rc"] = rc
        marker = any(ln.startswith("SUCCESS:") for ln in tail.splitlines())
        if rc != 0 or not marker:
            fails.append("probe-%s-rc:%d marker:%s tail:%s"
                         % (pid, rc, marker, tail[-240:]))
        else:
            notes.append("%s rc=0 SUCCESS-marker" % pid)

    # (8) output_schema via fail-closed repo resolver (subprocess = clean import state)
    try:
        r = subprocess.run(
            [sys.executable, "-I", str(RESOLVER), out_rel, schema_decl],
            capture_output=True, text=True, timeout=300, cwd=str(REPO),
            env=os.environ.copy())
        outline = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
        if r.returncode != 0 or "FAILED:" in outline:
            first = outline.splitlines()[0] if outline.splitlines() else outline[:120]
            fails.append("schema:%s" % first[:220])
        else:
            info["schema"] = "OK"
    except Exception as exc:
        fails.append("schema-resolver-error:%s:%s" % (type(exc).__name__, exc))

    # (9) canonical gate (its own transport)
    try:
        gr = subprocess.run([sys.executable, "-I", str(GATE), uid],
                            capture_output=True, text=True, timeout=2700,
                            cwd=str(REPO))
        gout = ((gr.stdout or "") + "\n" + (gr.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        gout = "TIMEOUT"
    glines = [ln for ln in gout.splitlines()
              if ln.startswith(("SUCCESS:delivered", "FAILED:delivered"))]
    info["gate"] = glines[-1] if glines else "no-verdict"
    if not (glines and glines[-1].startswith("SUCCESS:delivered")):
        fails.append("canonical-gate:" + info["gate"])

    # informational: receipt artifacts[] sha vs live files
    drift = []
    for a in doc.get("artifacts") or []:
        if not isinstance(a, dict):
            continue
        ap = str(a.get("path") or "").replace("\\", "/")
        sha = str(a.get("sha256") or "")
        if not ap or not sha:
            continue
        f = REPO / ap
        if not f.is_file():
            drift.append("missing:" + ap)
            continue
        live, _ = digest(f)
        if live != sha:
            drift.append("sha-drift:" + ap)
    if drift:
        info["receipt_artifact_drift"] = drift
        notes.append("INFO receipt-artifacts drift(%d): %s"
                     % (len(drift), "; ".join(drift[:4])))
    else:
        notes.append("receipt artifacts[] all match live files (%d rows)"
                     % len([a for a in doc.get("artifacts") or []
                            if isinstance(a, dict)]))
    info["notes"] = notes
    return (not fails), fails, info


def main():
    results = {}
    all_ok = True
    for uid in (sys.argv[1:] or IDS):
        ok, fails, info = verify(uid)
        results[uid] = {"ok": ok, "fails": fails, "info": info}
        all_ok = all_ok and ok
        print("== %s %s" % (uid, "OK" if ok else "FAIL"))
        print("   out=%s bytes=%s manifest_rows=%s state=%s verdict=%s indep=%s"
              % (info.get("out"), info.get("bytes"), info.get("manifest_rows"),
                 info.get("receipt_state"), info.get("reviewer_verdict"),
                 info.get("reviewer_independent")))
        print("   sha256=%s" % info.get("sha256"))
        prc = {k: v for k, v in info.items() if k.startswith("probe_")}
        if prc:
            print("   probe_rcs=%s" % prc)
        print("   schema=%s gate=%s" % (info.get("schema"), info.get("gate")))
        for n in info.get("notes", []):
            print("   note: %s" % n)
        for f in fails:
            print("   FAILCHECK: %s" % f)
        print("   %s:%s" % ("SUCCESS" if ok else "FAILED", uid))
        sys.stdout.flush()
    OUT.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    print("SUCCESS:review-w2s14 all 12 units verified" if all_ok
          else "FAILED:review-w2s14 one or more units red")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
