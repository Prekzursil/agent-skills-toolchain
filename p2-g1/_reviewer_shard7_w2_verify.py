#!/usr/bin/env python3
"""Independent reviewer verifier - wave 2 shard 7 (12 units).

Re-derives every contract check from bytes with a transport INDEPENDENT of the
canonical _measure_one_delivered.py (direct sys.executable subprocess, no shell
env-prefix adaptation, no g1_python wrapper):

  1. catalog entry resolves (live WORK-UNIT-CATALOG.json)
  2. artifact at output_path: exists / non-empty / parses / dict / not
     self-declared NOT-DELIVERING / completion sentinel present in text
  3. probes/<uid>/UNIT-ARTIFACT-MANIFEST.json: row for uid whose path ==
     output_path, present=true, sha256 == live sha (CRLF->LF normalized)
  4. both named probes re-run as direct subprocesses: rc==0 AND terminal
     SUCCESS: marker in output
  5. artifact validates against the catalog output_schema (jsonschema)
  6. receipt closure state read: state / reviewer.verdict / reviewer.independent

Prints per-unit blocks; exit 0 only if ALL units hold. Honest output: any
failing check names the unit and the exact failing predicate.
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
    "BLD-0043", "BLD-0044", "BLD-0045", "BLD-0049", "BLD-0050", "BLD-0058",
    "BLD-0059", "BLD-0061", "CC-0003", "CC-0010", "CC-0019", "CNF-0070",
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
    if sent and sent not in text:
        fails.append("completion-sentinel-absent")

    man_rel = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man, err = load(man_rel)
    if man is None:
        fails.append(f"manifest-unparseable:{err}")
    else:
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

    ret_rel = PROBES / uid / "SUBAGENT-RETURN.json"
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
        # de-quote the recorded POSIX command into script path token
        toks = cmd.split()
        script_rel = next((t for t in toks if t.endswith(".py")), None)
        if script_rel is None:
            fails.append(f"probe-command-unusable:{pid}")
            continue
        rc, tail = run_probe(script_rel)
        marker = "SUCCESS:" if rc == 0 else "FAILED:"
        has_marker = any(ln.startswith(("SUCCESS:", "FAILED:")) for ln in tail.splitlines())
        okp = rc == 0 and any(ln.startswith("SUCCESS:") for ln in tail.splitlines())
        info[f"probe_{pid}_rc"] = rc
        if not okp:
            fails.append(f"probe-{pid}-rc:{rc} marker:{has_marker} tail:{tail[-200:]}")

    schema_rel = str(unit.get("output_schema") or "").replace("\\", "/")
    schema_doc, err = load(REPO / schema_rel)
    if schema_doc is None:
        fails.append(f"schema-unreadable:{schema_rel}:{err}")
    else:
        try:
            cls = jsonschema.validators.validator_for(schema_doc)
            cls.check_schema(schema_doc)
            validator = cls(schema_doc)
            errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
            if errs:
                worst = errs[0]
                fails.append(
                    "schema-violations:%d first:%s at %s" % (
                        len(errs), worst.message[:220],
                        "/".join(str(x) for x in worst.absolute_path)[:120],
                    )
                )
            else:
                info["schema"] = f"OK:{schema_rel}"
        except jsonschema.SchemaError as exc:
            fails.append(f"schema-invalid:{exc.message[:160]}")

    r_state = str(doc.get("state") or "")
    rv = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
    info["receipt_state"] = r_state
    info["reviewer_verdict"] = rv.get("verdict")
    info["reviewer_independent"] = rv.get("independent")
    fail_block = doc.get("failure") if isinstance(doc.get("failure"), dict) else None
    if fail_block:
        cls_rows = [str(c) for c in fail_block.get("classification") or []]
        info["failure_classification"] = cls_rows
        if r_state.upper() == "SUCCESS" and "reviewer-absent" in cls_rows:
            fails.append("inconsistent:state=SUCCESS-with-reviewer-absent-classification")
    return (not fails), fails, info


def main() -> int:
    all_ok = True
    for uid in UNITS:
        ok, fails, info = verify(uid)
        all_ok = all_ok and ok
        print("== %s %s" % (uid, "OK" if ok else "FAIL"))
        print("   out=%s bytes=%s" % (info.get("out"), info.get("bytes")))
        print("   sha256=%s manifest_rows=%s" % (info.get("sha256"), info.get("manifest_rows")))
        prc = {k: v for k, v in info.items() if k.startswith("probe_")}
        if prc:
            print("   probe_rcs=%s" % prc)
        print("   schema=%s" % info.get("schema"))
        print("   receipt_state=%s reviewer_verdict=%s reviewer_independent=%s %s" % (
            info.get("receipt_state"), info.get("reviewer_verdict"),
            info.get("reviewer_independent"), info.get("failure_classification") or ""))
        for f in fails:
            print("   FAILCHECK: %s" % f)
        print("   %s:%s" % ("SUCCESS" if ok else "FAILED", uid))
    print("SUCCESS:reviewer-shard7-w2 all units verified" if all_ok
          else "FAILED:reviewer-shard7-w2 one or more units red")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
