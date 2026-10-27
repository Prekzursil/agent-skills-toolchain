#!/usr/bin/env python3
"""Independent reviewer verifier - wave 3 shard 8 (12 units).

w3s8 = CNF-0152, CNF-0164, CNF-0167, CNF-0169, CNF-0171, CNF-0172,
       CNF-0177, CNF-0184, CNF-0188, CNF-0191, CNL-0078, IMP-0002
(from _reviewer-w4s8/build-assignments-all-waves.json build:w3s8)

Transport INDEPENDENT of the builder's _measure_one_delivered.py: direct
sys.executable subprocesses, no shell env-prefix adaptation.

Per unit:
  1. catalog entry resolves (live WORK-UNIT-CATALOG.json)
  2. artifact at output_path: exists / non-empty / parses / dict / not
     self-declared NOT-DELIVERING / completion sentinel present in text
  3. output_schema validated: instance = output doc, schema = declared member
     (composite "A + B" handled)
  4. probes/<uid>/UNIT-ARTIFACT-MANIFEST.json: primary row path == output_path,
     present=true, sha256 == live CRLF->LF-normalized sha; secondary rows for
     declared schema members must match too; probe .py rows must match
  5. both named probes re-run live: rc==0 AND terminal SUCCESS: marker;
     artifact sha recomputed AFTER probes - must be unchanged (probe did not
     mutate the deliverable mid-review)
  6. closure doc rules: full receipt (receipts/<uid>.json) gets the complete
     receipt_core conditionals; envelope-only units (no receipt file; closure
     lives in SUBAGENT-RETURN.json per manifest receipt_path) get the core
     conditionals (not-DELIVERING, reviewer PASS + independent, registered,
     sentinel not FAILED).

Exit 0 only if ALL 12 units hold. Honest output: every failing check names
the unit and the exact failing predicate.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
UNITS = [
    "CNF-0152", "CNF-0164", "CNF-0167", "CNF-0169", "CNF-0171", "CNF-0172",
    "CNF-0177", "CNF-0184", "CNF-0188", "CNF-0191", "CNL-0078", "IMP-0002",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001 - verifier must see the reason
        return None, f"{type(exc).__name__}: {exc}"


def run_probe(script_rel: str) -> tuple[int, str]:
    p = REPO / script_rel
    if not p.is_file():
        return 127, f"probe script absent: {script_rel}"
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


def validate(doc, schema_path: Path):
    schema_doc, err = load(schema_path)
    if schema_doc is None:
        return f"schema-unreadable:{schema_path.name}:{err}"
    try:
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
        return f"schema-invalid:{exc.message[:160]}"
    except Exception as exc:  # noqa: BLE001
        return f"schema-resolution-error:{type(exc).__name__}:{exc}"
    return None


def receipt_core_closure_fails(doc: dict, envelope: bool) -> list[str]:
    """receipt_core conditionals. envelope=True relaxes the receipt-shape-only
    fields (evidence/tests/controls/consumers) that exist only on full
    receipts; the SUCCESS<->reviewer core rule always applies."""
    fails: list[str] = []
    st = str(doc.get("state") or doc.get("status") or "").upper()
    rv = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
    if st == "SUCCESS" or (envelope and st == "DELIVERED"):
        if rv.get("verdict") != "PASS":
            fails.append(f"closure:reviewer.verdict={rv.get('verdict')!r}!=PASS")
        if rv.get("independent") is not True:
            fails.append(f"closure:reviewer.independent={rv.get('independent')!r}!=true")
        mr = doc.get("manifest_registration")
        registered = (isinstance(mr, dict) and mr.get("registered") is True) \
            or doc.get("registered") is True
        if not registered:
            fails.append("closure:manifest_registration.registered!=true")
        if envelope:
            return fails  # core rule applied; receipt-shape fields not present
        ev = doc.get("evidence") or []
        if len(ev) < 2:
            fails.append(f"closure:evidence<2:{len(ev)}")
        for t in (doc.get("tests") or []):
            if isinstance(t, dict) and t.get("result") in ("FAIL", "ERROR", "SKIP", "NOT-RUN"):
                fails.append(f"closure:test-result:{t.get('result')}:{str(t.get('name'))[:60]}")
        nc = doc.get("negative_controls") or []
        if len(nc) < 1:
            fails.append("closure:negative_controls-empty")
        for c in nc:
            if isinstance(c, dict) and c.get("fired_on_bad_state") is False:
                fails.append("closure:control-not-fired-on-bad-state")
            if isinstance(c, dict) and c.get("silent_on_good_state") is False:
                fails.append("closure:control-not-silent-on-good-state")
        dc = doc.get("downstream_consumers") or []
        ok_dc = [d for d in dc if isinstance(d, dict)
                 and d.get("executed") is not False and d.get("read_ok") is not False]
        if len(ok_dc) < 1:
            fails.append("closure:no-executed-downstream-consumer")
        for d in (doc.get("defects") or []):
            if (isinstance(d, dict) and d.get("severity") in ("P0", "P1")
                    and d.get("status") == "open"):
                fails.append(f"closure:open-P0/P1-defect:{str(d.get('id'))[:40]}")
        fblock = doc.get("failure")
        if isinstance(fblock, dict):
            cls_rows = [str(c) for c in fblock.get("classification") or []]
            if "reviewer-absent" in cls_rows:
                fails.append("closure:SUCCESS-with-reviewer-absent-classification")
    elif st in NOT_DELIVERING:
        if not isinstance(doc.get("failure"), dict):
            fails.append("closure:terminal-failure-without-failure-block")
    else:
        fails.append(f"closure:unknown-state:{st!r}")
    sent = str(doc.get("sentinel") or "")
    if sent.startswith("FAILED:"):
        fails.append("closure:FAILED-sentinel")
    return fails


def verify(uid: str) -> tuple[bool, list[str], dict]:
    fails: list[str] = []
    info: dict = {"uid": uid}

    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    unit = next((u for u in cat["work_units"] if u.get("id") == uid), None)
    if unit is None:
        return False, ["catalog-entry-absent"], info

    out_rel = str(unit.get("output_path") or "").replace("\\", "/")
    out = REPO / out_rel
    info["out"] = out_rel
    if not out.is_file():
        return False, [f"artifact-absent:{out_rel}"], info
    size = out.stat().st_size
    info["bytes"] = size
    if size <= 0:
        fails.append("artifact-empty")
    text = out.read_text(encoding="utf-8", errors="replace")
    doc, err = load(out)
    if doc is None:
        fails.append(f"artifact-unparseable:{err}")
        return False, fails, info
    if not isinstance(doc, dict):
        fails.append("artifact-not-object")
        return False, fails, info
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        fails.append(f"self-declared:{st}")
    sent = str(unit.get("completion_sentinel") or "")
    if sent and sent.split()[0] not in text:
        fails.append("completion-sentinel-absent")

    pre_sha, _ = digest(out)

    # --- output_schema validation ---
    osch = str(unit.get("output_schema") or "")
    members = [m.strip() for m in osch.split("+") if m.strip()]
    for m in members:
        m_norm = m.replace("\\", "/")
        v = validate(doc, REPO / m_norm)
        if v:
            fails.append(f"output-schema:{m_norm}:{v}")
        else:
            info.setdefault("schema", []).append(f"OK:{m_norm}")

    # --- closure document ---
    receipt_path = REPO / "command-center" / "receipts" / f"{uid}.json"
    if receipt_path.is_file():
        closure_doc, closure_src, envelope = doc, "receipt", False
    else:
        ret_path = PROBES / uid / "SUBAGENT-RETURN.json"
        cdoc, cerr = load(ret_path)
        if cdoc is None:
            return False, [f"no-receipt-and-subagent-return-unreadable:{cerr}"], info
        closure_doc, closure_src, envelope = cdoc, "subagent-return", True
    info["closure_src"] = closure_src
    fails.extend(receipt_core_closure_fails(closure_doc, envelope))

    # --- manifest ---
    man_rel = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if not man_rel.is_file():
        fails.append("manifest-absent:" + str(man_rel.relative_to(REPO)).replace("\\", "/"))
        man = None
    else:
        man, err = load(man_rel)
        if man is None:
            fails.append(f"manifest-unparseable:{err}")
    if man is not None:
        rows = [a for a in man.get("artifacts") or []
                if isinstance(a, dict) and a.get("unit_id") == uid]
        info["manifest_rows"] = len(rows)
        live_sha, live_n = digest(out)
        info["sha256"] = live_sha
        ok_row = [a for a in rows
                  if str(a.get("path") or "").replace("\\", "/") == out_rel
                  and str(a.get("sha256") or "") == live_sha
                  and a.get("present") is True]
        if not ok_row:
            fails.append("manifest-sha-row-mismatch")
        schema_members = {m.replace("\\", "/") for m in members}
        for a in rows:
            rp = str(a.get("path") or "").replace("\\", "/")
            if rp in schema_members and rp != out_rel:
                f = REPO / rp
                if not f.is_file():
                    fails.append(f"manifest-secondary-absent:{rp}")
                else:
                    sha2, _ = digest(f)
                    if a.get("present") is not True or str(a.get("sha256") or "") != sha2:
                        fails.append(f"manifest-secondary-sha-mismatch:{rp}")
            elif rp.endswith(".py") and rp != out_rel:
                f = REPO / rp
                if not f.is_file():
                    fails.append(f"manifest-probe-script-absent:{rp}")
                else:
                    sha2, _ = digest(f)
                    if a.get("present") is not True or str(a.get("sha256") or "") != sha2:
                        fails.append(f"manifest-probe-script-sha-mismatch:{rp}")

    # --- probes: re-run live ---
    ret_rel = PROBES / uid / "SUBAGENT-RETURN.json"
    if not ret_rel.is_file():
        fails.append("subagent-return-absent")
        probes_cmds = []
    else:
        ret, err = load(ret_rel)
        if ret is None:
            fails.append(f"subagent-return-unparseable:{err}")
            probes_cmds = []
        else:
            rst = str(ret.get("status") or ret.get("state") or "").upper()
            if rst in NOT_DELIVERING:
                fails.append(f"subagent-return-state:{rst}")
            probes_cmds = [
                (p.get("id"), str(p.get("command") or ""))
                for p in (ret.get("named_probes") or []) if isinstance(p, dict)
            ]
            if len(probes_cmds) < 2:
                fails.append(f"named-probes<{2}:{len(probes_cmds)}")
    for pid, cmd in probes_cmds:
        toks = cmd.split()
        script_rel = next((t for t in toks if t.endswith(".py")), None)
        if script_rel is None:
            fails.append(f"probe-command-unusable:{pid}")
            continue
        rc, tail = run_probe(script_rel)
        info[f"probe_{pid}_rc"] = rc
        okp = rc == 0 and any(ln.startswith("SUCCESS:") for ln in tail.splitlines())
        if not okp:
            has_marker = any(ln.startswith(("SUCCESS:", "FAILED:")) for ln in tail.splitlines())
            fails.append(f"probe-{pid}-rc:{rc} marker:{has_marker} tail:{tail[-220:]}")

    # --- probe must not have mutated the deliverable ---
    post_sha, _ = digest(out)
    if post_sha != pre_sha:
        fails.append(f"artifact-mutated-by-probe-run:{pre_sha[:12]}->{post_sha[:12]}")

    info["receipt_state"] = closure_doc.get("state") or closure_doc.get("status")
    rv = closure_doc.get("reviewer") if isinstance(closure_doc.get("reviewer"), dict) else {}
    info["reviewer_verdict"] = rv.get("verdict")
    info["reviewer_independent"] = rv.get("independent")

    return (not fails), fails, info


def main() -> int:
    all_ok = True
    summary = {}
    for uid in UNITS:
        ok, fails, info = verify(uid)
        all_ok = all_ok and ok
        summary[uid] = {"ok": ok, "fails": fails, "info": info}
        print("== %s %s" % (uid, "OK" if ok else "FAIL"))
        print("   out=%s bytes=%s closure=%s" % (
            info.get("out"), info.get("bytes"), info.get("closure_src")))
        print("   sha256=%s manifest_rows=%s" % (
            info.get("sha256"), info.get("manifest_rows")))
        prc = {k: v for k, v in info.items() if k.startswith("probe_")}
        if prc:
            print("   probe_rcs=%s" % prc)
        print("   schema=%s" % info.get("schema"))
        print("   state=%s reviewer_verdict=%s reviewer_independent=%s" % (
            info.get("receipt_state"), info.get("reviewer_verdict"),
            info.get("reviewer_independent")))
        for f in fails:
            print("   FAILCHECK: %s" % f)
        print("   %s:%s" % ("SUCCESS" if ok else "FAILED", uid))
    out_path = REPO / "_reviewer_w3s8_verdicts.json"
    out_path.write_text(json.dumps({
        "reviewer": "wave-3-shard-8-independent (claude opus-5-5, fresh context)",
        "transport": "direct sys.executable subprocess, independent of builder _measure_one_delivered.py",
        "units": summary,
        "all_ok": all_ok,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("verdicts written: %s" % out_path)
    print("SUCCESS:reviewer-w3s8 all units verified" if all_ok
          else "FAILED:reviewer-w3s8 one or more units red")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
