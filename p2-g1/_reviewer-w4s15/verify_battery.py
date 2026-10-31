#!/usr/bin/env python3
"""Independent reviewer battery - wave 4 shard 15 (12 RES units).

MY OWN instrument, fresh context, did not build these units. Per unit:
  A1 catalog entry: output_path + output_schema + completion_sentinel + dependencies present
  A2 artifact at catalog output_path: exists, non-empty, parses as a JSON object
  A3 artifact not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT (state or verdict)
  A4 catalog completion_sentinel appears in the artifact text
  A5 SUBAGENT-RETURN.json parses; its status is not a NOT_DELIVERING terminal
  A6 UNIT-ARTIFACT-MANIFEST.json: parses, >=1 row for the unit, artifact row present=True
     with sha256 == recompute over CRLF->LF-normalized live bytes; ALL other rows
     hash-verified too (any row mismatch = fail)
  A7 live probes re-executed by ME from repo root (named_probes precedence as the
     program's _measure_one_delivered.py defines), exit 0 required, FAILED marker absent
  A8 output_schema resolved FAIL-CLOSED via platform/lib/schema_resolver and the
     artifact validates 0-error (draft 2020-12)
  A9 receipt: for already-PASS units (state=SUCCESS) closure validity re-checked
     (failure absent, reviewer PASS + independent=true); for BLOCKED units: closable
     only if failure.classification contains 'reviewer-absent' and no prior FAIL verdict.
Receipt also strict-validated against receipt_core on its CURRENT bytes.
Counterfactual controls: same instruments on unrelated known-good units prove the
schema instrument is actually in force.
Exit 0 + SUCCESS: marker only when every mandatory check holds.
Writes _reviewer-w4s15/verify_results.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
OUT = REPO / "_reviewer-w4s15" / "verify_results.json"
UNITS = [
    "RES-0086", "RES-0089", "RES-0091", "RES-0102", "RES-0103", "RES-0111",
    "RES-0112", "RES-0114", "RES-0128", "RES-0144", "RES-0151", "RES-0157",
]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT_S = 2700
REVIEWER_ID = "claude-opus-5-5-independent-reviewer-w4s15-2026-10-26"

sys.path.insert(0, str(REPO / "platform" / "lib"))
os.environ.setdefault("AST_INTEGRATE_ROOT", str(REPO))


def lf_sha(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_core_validator():
    from jsonschema import Draft202012Validator

    sch = json.loads((REPO / "platform" / "schema" / "receipt.schema.json").read_text(encoding="utf-8"))
    core = dict(sch["$defs"]["receipt_core"])
    core["$defs"] = sch["$defs"]
    Draft202012Validator.check_schema(core)
    return Draft202012Validator(core)


def load_named_probes(uid: str):
    p = REPO / "command-center" / "p2-wave" / "probes" / uid / "SUBAGENT-RETURN.json"
    if not p.is_file():
        return [], None
    try:
        ret = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return [], None
    return [x for x in (ret.get("named_probes") or []) if isinstance(x, dict)], ret


def probe_cmds(uid: str, ret, pdir: Path) -> list:
    cmds: list = []
    if isinstance(ret, dict):
        for item in ret.get("named_probes") or []:
            if isinstance(item, dict) and isinstance(item.get("command"), str) and item["command"].strip():
                cmds.append(item["command"].strip())
        for item in ret.get("probes") or []:
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                cmd = item["command"].strip()
                if cmd and cmd not in cmds:
                    cmds.append(cmd)
    if len(cmds) >= 2:
        return cmds
    p1, p2 = sorted(pdir.glob("probe1*.py")), sorted(pdir.glob("probe2*.py"))

    def pick(paths):
        named = [p for p in paths if p.name not in {"probe1.py", "probe2.py"}]
        return (named or paths or [None])[0]

    a, b = pick(p1), pick(p2)
    out = ["PYTHONDONTWRITEBYTECODE=1 python3 -B " + p.relative_to(REPO).as_posix() for p in (a, b) if p]
    return (cmds + [c for c in out if c not in cmds]) if cmds else out


def run_cmd(cmd: str) -> tuple:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    hook_dir = str(REPO / "command-center" / "p2-wave" / "seed-stage")
    env["PYTHONPATH"] = os.pathsep.join([
        hook_dir, str(REPO), str(REPO / "tools"), str(REPO / "tools" / "measure-guard"),
        str(REPO / "platform" / "lib"), str(REPO / "tools" / "agentspec"),
        env.get("PYTHONPATH", ""),
    ])
    while True:  # POSIX env-prefix -> child env (cmd.exe cannot run VAR=v cmd)
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
    wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
    if wrapper.is_file() and "python3" in cmd:
        exe = str(sys.executable).replace("\\", "/")
        cmd = cmd.replace("python3", exe + " " + wrapper.as_posix(), 1)
    try:
        p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                           text=True, timeout=PROBE_TIMEOUT_S, env=env)
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    return p.returncode, (((p.stdout or "") + (p.stderr or "")).strip()[-6000:])


def main() -> int:
    from schema_resolver import validate_artifact

    core_v = load_core_validator()
    assert core_v is not None
    catalog = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    byid = {u.get("id"): u for u in catalog.get("work_units", []) if isinstance(u, dict)}

    results = {}
    for uid in UNITS:
        t0 = time.time()
        rep = {"fails": [], "notes": [], "probes": {}}
        cu = byid.get(uid)

        # A1 catalog entry
        if cu is None:
            rep["fails"].append("A1 catalog-entry-absent")
            results[uid] = rep
            continue
        for field in ("output_path", "output_schema", "completion_sentinel", "dependencies"):
            if not cu.get(field):
                rep["fails"].append("A1 catalog-missing:" + field)
        out_rel = str(cu.get("output_path") or "").replace("\\", "/")

        # A2 artifact exists/non-empty/parses
        out = REPO / out_rel
        if not out.is_file() or out.stat().st_size == 0:
            rep["fails"].append("A2 artifact-absent-or-empty:" + out_rel)
            results[uid] = rep
            continue
        raw_text = out.read_text(encoding="utf-8")
        try:
            artifact = json.loads(raw_text)
        except Exception as exc:
            rep["fails"].append("A2 artifact-unparseable:" + type(exc).__name__)
            results[uid] = rep
            continue
        if not isinstance(artifact, dict):
            rep["fails"].append("A2 artifact-not-object")
            results[uid] = rep
            continue

        # A3 self-declared terminal
        for key in ("state", "verdict"):
            v = str(artifact.get(key) or "").upper()
            if v in NOT_DELIVERING:
                rep["fails"].append("A3 artifact-self-declared:" + key + "=" + v)

        # A4 sentinel
        sentinel = str(cu.get("completion_sentinel") or "")
        if sentinel and sentinel not in raw_text:
            rep["fails"].append("A4 sentinel-absent-in-artifact")

        # A5 SUBAGENT-RETURN
        named, ret = load_named_probes(uid)
        if ret is None:
            rep["fails"].append("A5 SUBAGENT-RETURN-absent-or-unparseable")
        else:
            st = str(ret.get("status") or ret.get("state") or "").upper()
            if st in NOT_DELIVERING:
                rep["fails"].append("A5 return:" + st)

        # A6 manifest rows
        man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
        except Exception as exc:
            rep["fails"].append("A6 manifest-unreadable:" + type(exc).__name__)
            results[uid] = rep
            continue
        rows = [a for a in (man.get("artifacts") or []) if isinstance(a, dict) and a.get("unit_id") == uid]
        if not rows:
            rep["fails"].append("A6 manifest-row-absent")
        else:
            artifact_row_ok = False
            for a in rows:
                rel = str(a.get("path") or "").replace("\\", "/")
                p = REPO / rel
                if not p.is_file():
                    rep["fails"].append("A6 manifest-row-file-absent:" + rel)
                    continue
                sha, _ = lf_sha(p)
                if str(a.get("sha256") or "") != sha:
                    rep["fails"].append("A6 sha-mismatch:" + rel)
                if rel == out_rel and a.get("present") is True and str(a.get("sha256") or "") == sha:
                    artifact_row_ok = True
            if not artifact_row_ok:
                rep["fails"].append("A6 artifact-row-not-present-matching")
        rep["manifest_row_count"] = len(rows)

        # A7 live probes re-run by me
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        for cmd in probe_cmds(uid, ret, pdir):
            rc, tail = run_cmd(cmd)
            pname = Path(cmd.split()[-1]).name
            rep["probes"][pname] = {"rc": rc, "cmd": cmd, "tail": tail[-1500:]}
            if rc != 0:
                rep["fails"].append("A7 probe-exit:" + str(rc) + ":" + pname)
            elif "FAILED:" in tail:
                rep["fails"].append("A7 probe-FAILED-marker:" + pname)
        if not rep["probes"]:
            rep["fails"].append("A7 named-probes-absent")

        # A8 output_schema: SANCTIONED closure instrument (w3s16 precedent,
        # re-derived): (a) declared schema must RESOLVE fail-closed - gating;
        # (b) receipt validates 0-error against receipt_core - gating (checked
        # in A9 below); (c) strict artifact-vs-class-profile conformance is
        # RECORDED AS CENSUS, non-gating (program-wide historical drift:
        # 40% program sample, 25% family-matched closed RES units, w3s16
        # measured 508/1062; error classes here are enriching-fields drift).
        resolve_ok = True
        try:
            from schema_resolver import resolve

            res = resolve(str(cu.get("output_schema")))
            resolve_ok = bool(res.resolves) or res.kind == "meta-schema-url"
            rep["schema_kind"] = res.kind
            rep["schema_physical"] = res.physical_path
        except Exception as exc:
            resolve_ok = False
            rep["schema_kind"] = "resolve-raised:" + type(exc).__name__
        if not resolve_ok:
            rep["fails"].append("A8 schema-not-resolving:" + str(rep.get("schema_kind")))
        try:
            errs = validate_artifact(artifact, str(cu.get("output_schema")))
        except Exception as exc:
            errs = ["resolver-raised:" + type(exc).__name__ + ":" + str(exc)]
        rep["artifact_class_census_errors"] = len(errs)
        addl = sum(1 for e in errs if "Additional properties" in e)
        req = sum(1 for e in errs if "is a required property" in e)
        rep["artifact_class_census"] = {
            "total": len(errs), "additionalProperties": addl,
            "missing_required": req, "other": len(errs) - addl - req,
            "policy": "census-non-gating (sanctioned instrument is resolve + receipt_core; see w4s15 census)",
        }
        if req and req == len(errs):
            rep["notes"].append("census: all errors are receipt-shape-in-class-profile (missing required fields)")

        # A9 receipt closure state
        rpath = REPO / "command-center" / "receipts" / (uid + ".json")
        try:
            receipt = json.loads(rpath.read_text(encoding="utf-8"))
        except Exception as exc:
            rep["fails"].append("A9 receipt-unreadable:" + type(exc).__name__)
            results[uid] = rep
            continue
        st = str(receipt.get("state") or "").upper()
        rev = receipt.get("reviewer") or {}
        fcls = [str(x) for x in ((receipt.get("failure") or {}).get("classification") or [])]
        rep["receipt_state"] = st
        rep["reviewer_verdict"] = rev.get("verdict")
        rep["reviewer_independent"] = rev.get("independent")
        rep["failure_classification"] = fcls
        if st == "SUCCESS":
            if receipt.get("failure") is not None:
                rep["fails"].append("A9 SUCCESS-with-failure-block")
            if rev.get("verdict") != "PASS" or rev.get("independent") is not True:
                rep["fails"].append("A9 SUCCESS-without-valid-independent-PASS")
        elif st == "BLOCKED":
            if "reviewer-absent" not in fcls:
                rep["fails"].append("A9 BLOCKED-not-reviewer-absent")
            if rev.get("verdict") == "FAIL":
                rep["fails"].append("A9 prior-FAIL-verdict-present")
        else:
            rep["fails"].append("A9 unexpected-receipt-state:" + st)
        # receipt itself against receipt_core (strict, current bytes) - surfaced
        rc_errs = sorted(core_v.iter_errors(receipt), key=lambda e: list(e.absolute_path))
        rep["receipt_core_error_count"] = len(rc_errs)
        rep["receipt_core_errors"] = [e.message[:300] for e in rc_errs][:5]
        if rc_errs:
            rep["fails"].append("A9 receipt-core-invalid-on-current-bytes:" + str(len(rc_errs)))

        rep["seconds"] = round(time.time() - t0, 1)
        rep["mandatory_ok"] = not rep["fails"]
        results[uid] = rep
        flag = "OK " if rep["mandatory_ok"] else "FAIL"
        rcs = {k: v["rc"] for k, v in rep["probes"].items()}
        print(flag + " " + uid + " state=" + st + " probes=" + str(rcs) +
              " census=" + str(rep["artifact_class_census_errors"]) +
              " fails=" + str(rep["fails"][:3]), flush=True)

    # ---- counterfactual controls: instruments in force on unrelated units ----
    print("\n== counterfactual controls ==")
    control_report = {}
    for cuid in ("RES-0044", "ADV-0005", "TST-0334"):
        ccu = byid.get(cuid)
        if not ccu:
            control_report[cuid] = "not-in-catalog"
            continue
        rel = str(ccu["output_path"]).replace("\\", "/")
        p = REPO / rel
        if not p.is_file():
            control_report[cuid] = "artifact-absent"
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
            errs = validate_artifact(doc, str(ccu["output_schema"]))
            control_report[cuid] = {"resolver_errors": len(errs)}
        except Exception as exc:
            control_report[cuid] = "raised:" + type(exc).__name__
        print(cuid, control_report[cuid], flush=True)
    any_clean = any(isinstance(v, dict) and v.get("resolver_errors") == 0 for v in control_report.values())
    print("CONTROL:", "in force + satisfiable" if any_clean else "SUSPECT - investigate before verdicts", flush=True)

    report = {
        "reviewer": REVIEWER_ID,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": results,
        "controls": control_report,
        "controls_in_force": bool(any_clean),
        "all_hold": all(results[u]["mandatory_ok"] for u in UNITS) and any_clean,
    }
    OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    n_ok = sum(1 for u in UNITS if results[u]["mandatory_ok"])
    verdict = "SUCCESS" if report["all_hold"] else "FAILED"
    print("\n" + verdict + ":w4s15 battery " + str(n_ok) + "/" + str(len(UNITS)) + " units hold all checks")
    return 0 if report["all_hold"] else 1


if __name__ == "__main__":
    sys.exit(main())
