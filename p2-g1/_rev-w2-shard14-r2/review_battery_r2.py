#!/usr/bin/env python3
"""Independent reviewer battery, wave 2 shard 14, ROUND 2 (fresh re-verification).

Written fresh for this review run. Does not import or execute the round-1
battery; the only shared components are the repo's OWN contract instruments
(schema_resolver.py, _measure_one_delivered.py), which any reviewer must use.

Checks per unit (ALL must hold for a PASS closure):
  1. catalog entry: output_path + output_schema (+ probes/dependencies/
     description keys recorded)
  2. artifact at output_path: exists / non-empty / parses / dict
  3. not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT and no
     UNIT-INCOMPLETE|UNIT-FAILED|NOT-DELIVERING text in bytes
  4. catalog completion_sentinel present in artifact text
  5. receipt_core closure rule: state=SUCCESS requires reviewer.verdict=PASS
     AND reviewer.independent=true; no contradictory failure block
  6. probes/<uid>/UNIT-ARTIFACT-MANIFEST.json: row unit_id==uid,
     path==output_path, present=true, sha256 == live CRLF->LF sha256
  7. SUBAGENT-RETURN.json: status/state not NOT-DELIVERING; >=2 named probes;
     BOTH re-run live by this reviewer (direct argv subprocess, transport
     independent of the gate wrapper): rc==0 required; SUCCESS-marker noted
  8. output_schema: fail-closed platform/lib/schema_resolver.py validation of
     the live artifact against the full decorated catalog declaration
  9. canonical gate _measure_one_delivered.py re-run: SUCCESS:delivered
Controls (both-states, prove the instruments are sensitive, not inert):
  C1. resolver positive control: command-center/receipts/CC-0003.json -> 0 errors
  C2. resolver negative control: same receipt minus a required field -> errors
  C3. digest negative control: tampered receipt copy -> digest differs from
      the untampered file (sha check can fail)

Any failing check -> FAIL verdict recorded; receipts are NOT modified by
this battery (fail-closed review: only a passing unit may be closed, and a
failing unit's receipt stays untouched).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
os.environ.setdefault("AST_INTEGRATE_ROOT", str(REPO))
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
GATE = REPO / "command-center" / "p2-wave" / "_measure_one_delivered.py"
RESOLVER = REPO / "platform" / "lib" / "schema_resolver.py"
HERE = REPO / "_rev-w2-shard14-r2"
TMP = HERE / "tmp"
OUT = HERE / "results-r2.json"
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


def run_argv(rel_script: str, timeout: int = 600):
    """Transport A: direct argv subprocess, no shell, no wrapper."""
    p = REPO / rel_script
    if not p.is_file():
        return 127, "script absent: " + rel_script
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    try:
        r = subprocess.run([sys.executable, "-B", str(p)],
                           capture_output=True, text=True, timeout=timeout,
                           cwd=str(REPO), env=env)
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT after %ds" % timeout
    return r.returncode, ((r.stdout or "") + "\n" + (r.stderr or "")).strip()


def run_resolver(artifact_rel: str, decl: str):
    """Fail-closed schema validation via the repo's blessed resolver."""
    try:
        r = subprocess.run(
            [sys.executable, "-I", str(RESOLVER), artifact_rel, decl],
            capture_output=True, text=True, timeout=300, cwd=str(REPO),
            env=os.environ.copy())
    except subprocess.TimeoutExpired:
        return 124, ["resolver-TIMEOUT"], ""
    outline = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
    errs = [ln for ln in outline.splitlines()
            if ln.strip() and not ln.startswith(("SUCCESS:", "FAILED:"))]
    failed = r.returncode != 0 or "FAILED:" in outline
    return r.returncode, (errs if failed else []), outline[:400]


def resolution_details(decl: str):
    """Ask the resolver (as a module) HOW the declaration resolves."""
    code = (
        "import json,sys;"
        "sys.path.insert(0,r'%s');"
        "from schema_resolver import resolve;"
        "r=resolve(%r);"
        "print(json.dumps(r.as_dict()))" % (str(REPO / "platform" / "lib"), decl)
    )
    try:
        r = subprocess.run([sys.executable, "-I", "-c", code],
                           capture_output=True, text=True, timeout=120,
                           cwd=str(REPO), env=os.environ.copy())
        if r.returncode == 0:
            return json.loads(r.stdout.strip())
        return {"error": (r.stderr or r.stdout).strip()[:300]}
    except Exception as exc:
        return {"error": "%s: %s" % (type(exc).__name__, exc)}


def probe_pairs(ret):
    pairs = []
    for item in ret.get("named_probes") or []:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("id") or "probe")
        cmd = str(item.get("command") or "")
        pys = [t for t in cmd.split() if t.endswith(".py")]
        pairs.append((pid, pys[-1].replace("\\", "/") if pys else ""))
    return pairs


def controls():
    """Both-states control battery. Returns dict; fails are recorded."""
    ctl = {}
    # C1 positive: a known-canonical receipt validates clean.
    rc, errs, tail = run_resolver("command-center/receipts/CC-0003.json",
                                  "command-center/schema/receipt.schema.json")
    ctl["C1_positive_CC0003"] = {
        "rc": rc, "errors": errs, "ok": (rc == 0 and not errs), "tail": tail}
    # C2 negative: same receipt, required field deleted, must FAIL.
    doc, err = loadj(REPO / "command-center" / "receipts" / "CC-0003.json")
    if doc is None:
        ctl["C2_negative"] = {"ok": False, "reason": "control-unreadable:" + str(err)}
    else:
        doc.pop("spec_anchor", None)
        p = TMP / "CC-0003-mutated.json"
        p.write_text(json.dumps(doc), encoding="utf-8")
        rc2, errs2, _ = run_resolver("_rev-w2-shard14-r2/tmp/CC-0003-mutated.json",
                                     "command-center/schema/receipt.schema.json")
        ctl["C2_negative"] = {"rc": rc2, "errors": errs2[:3],
                              "ok": (rc2 != 0 and len(errs2) > 0)}
    # C3 digest negative: tampered copy must change the digest.
    src = REPO / "command-center" / "receipts" / "CC-0003.json"
    good, _ = digest(src)
    p = TMP / "CC-0003-tampered.json"
    raw = src.read_bytes()
    p.write_bytes(raw + b"\n")
    bad, _ = digest(p)
    ctl["C3_digest_negative"] = {"ok": good != bad, "good": good[:12], "bad": bad[:12]}
    return ctl


def verify(uid: str, unit: dict):
    fails, notes, info = [], [], {"uid": uid}

    out_rel = str(unit.get("output_path") or "").replace("\\", "/")
    schema_decl = str(unit.get("output_schema") or "")
    if not out_rel or not schema_decl:
        return False, ["catalog-row-missing-output_path-or-output_schema"], info
    info["out"] = out_rel
    info["schema_decl"] = schema_decl[:160]
    info["catalog_keys_present"] = {
        k: (k in unit) for k in ("probes", "dependencies", "description")}

    # (2)(3)(4) artifact checks
    out = REPO / out_rel
    if not out.is_file():
        return False, ["artifact-absent:" + out_rel], info
    size = out.stat().st_size
    info["bytes"] = size
    if size <= 0:
        fails.append("artifact-empty")
    doc, err = loadj(out)
    if doc is None:
        return False, fails + ["artifact-unparseable:" + str(err)], info
    if not isinstance(doc, dict):
        return False, fails + ["artifact-not-object"], info
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

    # (5) receipt_core closure rule
    rv = doc.get("reviewer") or {}
    info["reviewer_verdict"] = rv.get("verdict")
    info["reviewer_independent"] = rv.get("independent")
    info["reviewer_id"] = rv.get("reviewer_id")
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
        info["manifest_sha"] = next(
            (a.get("sha256") for a in rows
             if str(a.get("path") or "").replace("\\", "/") == out_rel), None)
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
        if len([x for x in pairs if x[1]]) < 2:
            fails.append("named-probes<2:%d" % len(pairs))
    for pid, rel in pairs:
        if not rel:
            fails.append("probe-command-unusable:" + pid)
            continue
        rc, tail = run_argv(rel)
        info["probe_%s_rc" % pid] = rc
        marker = any(ln.startswith("SUCCESS:") for ln in tail.splitlines())
        info["probe_%s_marker" % pid] = marker
        if rc != 0:
            fails.append("probe-%s-rc:%d tail:%s" % (pid, rc, tail[-200:]))
        elif not marker:
            notes.append("%s rc=0 WITHOUT SUCCESS-marker (rc0 is the contract "
                         "gate; recorded as note)" % pid)
        else:
            notes.append("%s rc=0 SUCCESS-marker" % pid)

    # (8) output_schema via fail-closed repo resolver
    rrc, rerrs, rtail = run_resolver(out_rel, schema_decl)
    info["schema_rc"] = rrc
    info["schema_error_count"] = len(rerrs)
    info["schema_first_errors"] = rerrs[:4]
    info["schema_resolution"] = resolution_details(schema_decl)
    if rrc != 0 or rerrs:
        fails.append("schema:%s" % (rerrs[0][:220] if rerrs else rtail[:220]))

    # (9) canonical gate (its own transport)
    try:
        gr = subprocess.run([sys.executable, "-I", str(GATE), uid],
                            capture_output=True, text=True, timeout=2700,
                            cwd=str(REPO), env=os.environ.copy())
        gout = ((gr.stdout or "") + "\n" + (gr.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        gout = "TIMEOUT"
    glines = [ln for ln in gout.splitlines()
              if ln.startswith(("SUCCESS:delivered", "FAILED:delivered"))]
    info["gate"] = glines[-1] if glines else "no-verdict"
    if not (glines and glines[-1].startswith("SUCCESS:delivered")):
        fails.append("canonical-gate:" + info["gate"])

    info["notes"] = notes
    return (not fails), fails, info


def main():
    cat, err = loadj(CATALOG)
    if cat is None:
        print("FAILED:battery catalog-unreadable: %s" % err)
        return 1
    units = {u.get("id"): u for u in cat.get("work_units") or []}

    ctl = controls()
    print("CONTROLS:", json.dumps(
        {k: v.get("ok") for k, v in ctl.items()}))
    ctl_ok = all(v.get("ok") for v in ctl.values())
    if not ctl_ok:
        print("FAILED:controls instrument not proven sensitive: %s"
              % json.dumps(ctl)[:600])
        OUT.write_text(json.dumps({"controls": ctl, "aborted": True}, indent=1),
                       encoding="utf-8")
        return 1
    shutil.rmtree(TMP, ignore_errors=True)

    results = {}
    all_ok = True
    for uid in IDS:
        unit = units.get(uid)
        if unit is None:
            results[uid] = {"ok": False, "fails": ["catalog-entry-absent"]}
            all_ok = False
            print("== %s FAIL catalog-entry-absent" % uid)
            continue
        ok, fails, info = verify(uid, unit)
        results[uid] = {"ok": ok, "fails": fails, "info": info}
        all_ok = all_ok and ok
        print("== %s %s" % (uid, "OK" if ok else "FAIL"))
        print("   out=%s bytes=%s manifest_rows=%s state=%s verdict=%s indep=%s"
              % (info.get("out"), info.get("bytes"), info.get("manifest_rows"),
                 info.get("receipt_state"), info.get("reviewer_verdict"),
                 info.get("reviewer_independent")))
        print("   sha256=%s" % info.get("sha256"))
        print("   schema_errors=%s resolution=%s/%s" % (
            info.get("schema_error_count"),
            (info.get("schema_resolution") or {}).get("physical_path"),
            (info.get("schema_resolution") or {}).get("physical_fragment")))
        prc = {k: v for k, v in info.items()
               if k.startswith("probe_") and k.endswith("_rc")}
        print("   probe_rcs=%s gate=%s" % (prc, info.get("gate")))
        for n in info.get("notes", []):
            print("   note: %s" % n)
        for f in fails:
            print("   FAILCHECK: %s" % f)
        print("   %s:%s" % ("SUCCESS" if ok else "FAILED", uid))
        sys.stdout.flush()
    results["_controls"] = ctl
    results["_all_ok"] = all_ok
    OUT.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    print("SUCCESS:review-w2s14-r2 all 12 units verified" if all_ok
          else "FAILED:review-w2s14-r2 one or more units red")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
