#!/usr/bin/env python3
"""Independent reviewer verifier - wave 4 shard 22 (12 TST units).

Fresh-context re-derivation of the shard-7 w4 transport: every check re-run
from bytes via direct sys.executable subprocess, independent of the builder
_measure_one_delivered.py.

HARD contract checks per unit:
  1. artifact at catalog output_path: exists / non-empty / parses (JSON) /
     object / not self-declared BLOCKED|FAILED|SEVERED|TIMEOUT /
     completion sentinel present in text
  2. command-center/p2-wave/probes/<uid>/UNIT-ARTIFACT-MANIFEST.json: row whose
     path == output_path, present=true, sha256 == live sha256 (CRLF->LF normalized)
  3. named probes re-run live: rc==0 AND terminal SUCCESS: marker
     (or explicit all_ok/ok=true JSON)
  4. output_schema validated against the receipt (jsonschema, strict,
     fragment-aware: #/$defs/X overrides the root $ref)
  5. receipt_core closure: state=SUCCESS => reviewer.verdict=PASS AND
     reviewer.independent=true; conditional rules on fields present
Mutation guard: receipt sha256 snapshotted before/after probe runs.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema

REPO = Path("C:/Users/Prekzursil/p2-g1")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
UNITS = [
    "TST-0247", "TST-0249", "TST-0255", "TST-0256", "TST-0261", "TST-0265",
    "TST-0282", "TST-0283", "TST-0284", "TST-0288", "TST-0297", "TST-0303",
]


def digest(path):
    raw = path.read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm), len(raw)


def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001 - verifier must see the reason
        return None, "%s: %s" % (type(exc).__name__, exc)


def run_probe(script_rel):
    p = REPO / script_rel
    if not p.is_file():
        return 127, "probe script absent: %s" % script_rel
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        r = subprocess.run(
            [sys.executable, "-B", str(p)],
            capture_output=True, text=True, timeout=900,
            cwd=str(REPO), env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def probe_out_ok(rc, tail):
    if rc != 0:
        return False, "rc!=0"
    for ln in tail.splitlines():
        if ln.strip().startswith("SUCCESS:"):
            return True, "SUCCESS-marker"
    if '"all_ok": false' in tail or '"ok": false' in tail:
        return False, "json-ok-false"
    if '"all_ok": true' in tail or '"ok": true' in tail:
        return True, "json-ok-true"
    return False, "no-terminal-marker"


def validate(doc, schema_path, fragment):
    schema_doc, err = load(schema_path)
    if schema_doc is None:
        return "schema-unreadable:%s:%s" % (schema_path.name, err)
    try:
        if fragment:
            # fragment-aware: point the root $ref at the requested $defs member
            schema_doc = dict(schema_doc)
            schema_doc["$ref"] = fragment
        cls = jsonschema.validators.validator_for(schema_doc)
        cls.check_schema(schema_doc)
        validator = cls(schema_doc)
        errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
        if errs:
            w = errs[0]
            return ("schema-violations:%d first:%s at %s" % (
                len(errs), w.message[:200],
                "/".join(str(x) for x in w.absolute_path)[:100]))
    except jsonschema.SchemaError as exc:
        return "schema-invalid:%s" % exc.message[:160]
    except Exception as exc:  # noqa: BLE001
        return "schema-resolution-error:%s:%s" % (type(exc).__name__, exc)
    return None


def closure_fails(doc):
    fails = []
    st = str(doc.get("state") or "").upper()
    rv = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
    if st == "SUCCESS":
        if rv.get("verdict") != "PASS":
            fails.append("closure:reviewer.verdict=%r!=PASS" % rv.get("verdict"))
        if rv.get("independent") is not True:
            fails.append("closure:reviewer.independent=%r!=true" % rv.get("independent"))
        mr = doc.get("manifest_registration")
        if mr is not None and not (isinstance(mr, dict) and mr.get("registered") is True):
            fails.append("closure:manifest_registration.registered!=true")
        if "evidence" in doc:
            ev = doc.get("evidence") or []
            if not isinstance(ev, list) or len(ev) < 2:
                fails.append("closure:evidence<2:%s" % (len(ev) if isinstance(ev, list) else "non-list"))
        for t in (doc.get("tests") or []):
            if isinstance(t, dict) and t.get("result") in ("FAIL", "ERROR", "SKIP", "NOT-RUN"):
                fails.append("closure:test-result:%s:%s" % (t.get("result"), str(t.get("name"))[:60]))
        if "negative_controls" in doc:
            nc = doc.get("negative_controls") or []
            if isinstance(nc, list):
                if len(nc) < 1:
                    fails.append("closure:negative_controls-empty")
                for c in nc:
                    if isinstance(c, dict) and c.get("fired_on_bad_state") is False:
                        fails.append("closure:control-not-fired-on-bad-state")
                    if isinstance(c, dict) and c.get("silent_on_good_state") is False:
                        fails.append("closure:control-not-silent-on-good-state")
        if "downstream_consumers" in doc:
            dc = doc.get("downstream_consumers") or []
            ok_dc = [d for d in dc if isinstance(d, dict)
                     and d.get("executed") is not False and d.get("read_ok") is not False]
            if len(ok_dc) < 1:
                fails.append("closure:no-executed-downstream-consumer")
        for d in (doc.get("defects") or []):
            if (isinstance(d, dict) and d.get("severity") in ("P0", "P1")
                    and d.get("status") == "open"):
                fails.append("closure:open-P0/P1-defect:%s" % str(d.get("id"))[:40])
        fblock = doc.get("failure")
        if isinstance(fblock, dict):
            cls_rows = [str(c) for c in fblock.get("classification") or []]
            if "reviewer-absent" in cls_rows:
                fails.append("closure:SUCCESS-with-reviewer-absent-classification")
        sent = str(doc.get("sentinel") or "")
        if sent.startswith("FAILED:"):
            fails.append("closure:FAILED-sentinel-under-SUCCESS")
    elif st in NOT_DELIVERING:
        if not isinstance(doc.get("failure"), dict):
            fails.append("closure:terminal-failure-without-failure-block")
    return fails


def verify(uid):
    fails = []
    notes = []
    info = {"uid": uid}

    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    unit = next((u for u in cat["work_units"] if u.get("id") == uid), None)
    if unit is None:
        return False, ["catalog-entry-absent"], notes, info

    out_rel = str(unit.get("output_path") or "").replace("\\", "/")
    out = REPO / out_rel
    info["out"] = out_rel
    if not out.is_file():
        return False, ["artifact-absent:" + out_rel], notes, info
    sha0, n0, raw0 = digest(out)
    info["bytes_raw"], info["bytes_lf"], info["sha256"] = raw0, n0, sha0
    if raw0 <= 0:
        fails.append("artifact-empty")
    text = out.read_text(encoding="utf-8", errors="replace")
    doc, err = load(out)
    if doc is None:
        fails.append("artifact-unparseable:%s" % err)
        return False, fails, notes, info
    if not isinstance(doc, dict):
        fails.append("artifact-not-object")
        return False, fails, notes, info
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        fails.append("self-declared:%s" % st)
    sent = str(unit.get("completion_sentinel") or "")
    if sent and sent not in text:
        fails.append("completion-sentinel-absent")

    osch = str(unit.get("output_schema") or "")
    frag = None
    if "#" in osch:
        osch, frag = osch.split("#", 1)
        frag = "#" + frag
    osch_norm = osch.replace("\\", "/")
    if osch_norm.endswith(".json"):
        v = validate(doc, REPO / osch_norm, frag)
        if v:
            fails.append("receipt-schema:%s%s:%s" % (osch_norm, frag or "", v))
        else:
            info["schema"] = "OK:%s%s" % (osch_norm, frag or "")

    man_rel = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = None
    if not man_rel.is_file():
        fails.append("manifest-absent:%s" % str(man_rel.relative_to(REPO)).replace("\\", "/"))
    else:
        man, err = load(man_rel)
        if man is None:
            fails.append("manifest-unparseable:%s" % err)
    if man is not None:
        rows = [a for a in man.get("artifacts") or [] if isinstance(a, dict)]
        info["manifest_rows"] = len(rows)
        ok_row = [a for a in rows
                  if str(a.get("path") or "").replace("\\", "/") == out_rel
                  and str(a.get("sha256") or "") == sha0
                  and a.get("present") is not False]
        if not ok_row:
            got = [(a.get("path"), a.get("sha256")) for a in rows
                   if str(a.get("path") or "").replace("\\", "/") == out_rel]
            fails.append("manifest-sha-row-mismatch:expected:%s:got:%s" % (sha0, got))
        for a in rows:
            rp = str(a.get("path") or "").replace("\\", "/")
            if rp == out_rel:
                continue
            f = REPO / rp
            if not f.is_file():
                notes.append("row-file-absent:" + rp)
                continue
            sha2, _, _ = digest(f)
            if str(a.get("sha256") or "") != sha2:
                notes.append("row-stale:%s:manifest:%s:live:%s" % (
                    rp, str(a.get("sha256"))[:12], sha2[:12]))

    # --- probes: re-run live (from SUBAGENT-RETURN named_probes) ---
    ret_rel = PROBES / uid / "SUBAGENT-RETURN.json"
    probes_cmds = []
    if not ret_rel.is_file():
        fails.append("subagent-return-absent:%s" % str(ret_rel.relative_to(REPO)).replace("\\", "/"))
    else:
        ret, err = load(ret_rel)
        if ret is None:
            fails.append("subagent-return-unparseable:%s" % err)
        else:
            rst = str(ret.get("status") or ret.get("state") or "").upper()
            if rst in NOT_DELIVERING:
                fails.append("subagent-return-state:%s" % rst)
            probes_cmds = [
                (p.get("id"), str(p.get("command") or ""))
                for p in (ret.get("named_probes") or []) if isinstance(p, dict)
            ]
            if len(probes_cmds) < 2:
                fails.append("named-probes<2:%s" % len(probes_cmds))
    for pid, cmd in probes_cmds:
        toks = cmd.split()
        script_rel = next((t for t in toks if t.endswith(".py")), None)
        if script_rel is None:
            fails.append("probe-command-unusable:%s" % pid)
            continue
        rc, tail = run_probe(script_rel)
        okp, why = probe_out_ok(rc, tail)
        info["probe_%s_rc" % pid] = rc
        info["probe_%s_ok" % pid] = why
        if not okp:
            fails.append("probe-%s-rc:%s why:%s tail:%s" % (pid, rc, why, tail[-220:]))

    sha1, _, _ = digest(out)
    if sha1 != sha0:
        fails.append("receipt-mutated-during-verification:%s->%s" % (sha0[:12], sha1[:12]))

    fails.extend(closure_fails(doc))
    rv = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
    info["receipt_state"] = doc.get("state")
    info["reviewer_verdict"] = rv.get("verdict")
    info["reviewer_independent"] = rv.get("independent")
    return (not fails), fails, notes, info


def main():
    all_ok = True
    summary = {}
    for uid in UNITS:
        ok, fails, notes, info = verify(uid)
        all_ok = all_ok and ok
        summary[uid] = {"ok": ok, "fails": fails, "notes": notes, "info": info}
        print("== %s %s" % (uid, "OK" if ok else "FAIL"), flush=True)
        print("   out=%s raw=%s lf=%s" % (info.get("out"), info.get("bytes_raw"), info.get("bytes_lf")))
        print("   sha256=%s manifest_rows=%s" % (info.get("sha256"), info.get("manifest_rows")))
        prc = {k: v for k, v in info.items() if k.startswith("probe_")}
        if prc:
            print("   probes=%s" % prc)
        print("   schema=%s" % info.get("schema"))
        print("   receipt_state=%s reviewer_verdict=%s reviewer_independent=%s" % (
            info.get("receipt_state"), info.get("reviewer_verdict"),
            info.get("reviewer_independent")))
        for f in fails:
            print("   FAILCHECK: %s" % f)
        for n in notes:
            print("   note: %s" % n)
        print("   %s:%s" % ("SUCCESS" if ok else "FAILED", uid), flush=True)
    out_path = REPO / "_reviewer_w4s22_verdicts.json"
    out_path.write_text(json.dumps({
        "reviewer": "wave-4-shard-22-independent (claude opus-5-5, fresh context)",
        "transport": "direct sys.executable subprocess, independent of builder _measure_one_delivered.py",
        "units": summary,
        "all_ok": all_ok,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("verdicts written: %s" % out_path)
    print("SUCCESS:reviewer-w4s22 all units verified" if all_ok
          else "FAILED:reviewer-w4s22 one or more units red")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
