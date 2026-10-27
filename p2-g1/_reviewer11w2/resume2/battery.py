#!/usr/bin/env python3
"""INDEPENDENT REVIEWER battery - wave 2 shard 11 RESUME (2026-10-25, second run).

Fresh-context adversarial verification over all 12 shard-11 units, written by
this reviewer session (not a rerun of the builder's battery). Per unit:
  1 catalog      unit present in WORK-UNIT-CATALOG.json with output_path
  2 artifact     exists / non-empty / parses / completion_sentinel in text
  3 state        SUCCESS => reviewer PASS+independent; BLOCKED+reviewer-absent
                 => CLOSE-CANDIDATE; other self-declared not-delivering => FAIL
  4 probes       re-run named probes MYSELF (exit 0, no FAILED marker in output)
  5 manifest     sha256 (CRLF->LF) of live artifact == UNIT-ARTIFACT-MANIFEST row
  6 schema       platform receipt_schema_gate layer-1 errors == []
                 (+ IMP-0096: attachment vs benchmark-evidence schema)
  7 gate         12-condition predicate + coherence on the CURRENT bytes
  8 measure      the program's own _measure_one_delivered.py as a second signal
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

REPO = Path.home() / "p2-g1"
HERE = Path(__file__).resolve().parent
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
UNITS = ["IMP-0095", "IMP-0096", "IMP-0102", "IMP-0107", "IMP-0122",
         "IMP-0133", "IMP-0138", "IMP-0146", "IMP-0151", "IMP-0153",
         "IMP-0160", "IMP-0161"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


RSG = load_module("rsg_resume2", REPO / "platform" / "lib" / "receipt_schema_gate.py")


def digest_lf(p: Path):
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str, timeout: int = 900):
    """Run a probe/measure command verbatim (env-prefix aware, Windows-safe)."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    hook_dir = str(REPO / "command-center" / "p2-wave" / "seed-stage")
    env["PYTHONPATH"] = os.pathsep.join([
        hook_dir, str(REPO), str(REPO / "tools"),
        str(REPO / "tools" / "measure-guard"), str(REPO / "platform" / "lib"),
        str(REPO / "tools" / "agentspec"), env.get("PYTHONPATH", ""),
    ])
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
    wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
    if wrapper.is_file() and "python3" in cmd:
        exe = str(sys.executable).replace("\\", "/")
        cmd = cmd.replace("python3", f"{exe} {wrapper.as_posix()}", 1)
    elif "python3" in cmd:
        exe = str(sys.executable).replace("\\", "/")
        cmd = cmd.replace("python3", f'"{exe}"', 1)
    elif "python " in cmd:
        cmd = cmd.replace("python ", f'"{sys.executable}" ', 1)
    try:
        p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    tail = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, tail[-6000:]


def probe_commands(uid: str, ret: dict | None, probe_dir: Path) -> list[str]:
    cmds: list[str] = []
    if isinstance(ret, dict):
        for item in ret.get("named_probes") or []:
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                c = item["command"].strip()
                if c and c not in cmds:
                    cmds.append(c)
        for item in ret.get("probes") or []:
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                c = item["command"].strip()
                if c and c not in cmds:
                    cmds.append(c)
    if len(cmds) >= 2:
        return cmds[:2]
    p1 = sorted(probe_dir.glob("probe1*.py"))
    p2 = sorted(probe_dir.glob("probe2*.py"))

    def pick(paths):
        named = [x for x in paths if x.name not in {"probe1.py", "probe2.py"}]
        return (named or paths or [None])[0]

    a, b = pick(p1), pick(p2)
    out = []
    for x in (a, b):
        if x is not None:
            out.append(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {x.relative_to(REPO).as_posix()}")
    return out


def main() -> int:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    wu = {u.get("id"): u for u in cat.get("work_units") or []}
    report = {}
    ok_all = True
    for uid in UNITS:
        unit = wu.get(uid)
        checks = {}
        live = {}
        if unit is None:
            checks["catalog"] = "FAIL:catalog-missing"
            report[uid] = {"checks": checks, "verdict": "FAIL"}
            ok_all = False
            continue
        checks["catalog"] = "OK"
        out_rel = str(unit.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel
        # 2 artifact
        if not out.is_file() or out.stat().st_size <= 0:
            checks["artifact"] = "FAIL:absent-or-empty"
        else:
            try:
                text = out.read_text(encoding="utf-8")
                doc = json.loads(text)
                sent = str(unit.get("completion_sentinel") or "")
                if sent and sent not in text:
                    checks["artifact"] = "FAIL:sentinel-absent"
                else:
                    checks["artifact"] = "OK"
            except Exception as exc:
                checks["artifact"] = f"FAIL:unparseable:{type(exc).__name__}"
                doc = None
        # 3 state semantics
        if isinstance(doc, dict):
            st = str(doc.get("state") or "").upper()
            rv = doc.get("reviewer") or {}
            if st == "SUCCESS":
                if str(rv.get("verdict") or "").upper() == "PASS" and rv.get("independent") is True:
                    checks["state"] = "OK:closed"
                else:
                    checks["state"] = "FAIL:success-without-independent-pass"
            elif st == "BLOCKED":
                fc = (doc.get("failure") or {}).get("classification") or []
                if "reviewer-absent" in [str(x) for x in fc]:
                    checks["state"] = "CLOSE-CANDIDATE"
                else:
                    checks["state"] = f"FAIL:self-declared-BLOCKED({fc})"
            else:
                checks["state"] = f"FAIL:state={st}"
        else:
            checks["state"] = "FAIL:no-doc"
        # 4 probes - I run them myself, fresh
        probe_dir = PROBES / uid
        ret_path = probe_dir / "SUBAGENT-RETURN.json"
        ret = None
        if ret_path.is_file():
            try:
                ret = json.loads(ret_path.read_text(encoding="utf-8"))
            except Exception:
                ret = None
        cmds = probe_commands(uid, ret, probe_dir)
        live["probe_cmds"] = cmds
        live["probe_results"] = []
        if len(cmds) < 1:
            checks["probes"] = "FAIL:named-probes-absent"
        else:
            bad = []
            for i, c in enumerate(cmds, 1):
                rc, tail = run_cmd(c)
                failed_marker = bool(re.search(r"^FAILED:", tail, re.M))
                live["probe_results"].append({"cmd": c, "rc": rc,
                                              "failed_marker": failed_marker,
                                              "tail": tail[-1200:]})
                if rc != 0 or failed_marker:
                    bad.append(f"probe{i}:rc={rc},failed={failed_marker}")
            checks["probes"] = "OK" if not bad else "FAIL:" + ";".join(bad)
        # 5 manifest sha
        man_path = probe_dir / "UNIT-ARTIFACT-MANIFEST.json"
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
            rows = [a for a in (man.get("artifacts") or [])
                    if isinstance(a, dict) and a.get("unit_id") == uid]
            live_sha, live_bytes = digest_lf(out)
            live["sha"] = live_sha
            live["bytes"] = live_bytes
            match = any(str(a.get("path") or "").replace("\\", "/") == out_rel
                        and str(a.get("sha256") or "") == live_sha
                        and a.get("present") is True for a in rows)
            checks["manifest_sha"] = "OK" if match else (
                f"FAIL:mismatch live={live_sha[:12]} rows=" +
                ";".join(str(a.get('sha256'))[:12] for a in rows if a.get('path') == out_rel))
        except FileNotFoundError:
            checks["manifest_sha"] = "FAIL:manifest-missing"
        except Exception as exc:
            checks["manifest_sha"] = f"FAIL:{type(exc).__name__}"
        # 6 schema (layer 1)
        try:
            errs = RSG.validate_receipt(doc)
            checks["schema"] = "OK" if not errs else "FAIL:" + " | ".join(errs[:4])
        except Exception as exc:
            checks["schema"] = f"FAIL:{type(exc).__name__}:{exc}"
        # IMP-0096 second schema on the attachment
        if uid == "IMP-0096":
            try:
                bs = json.loads((REPO / "tools/marketplace/schema/benchmark-evidence.schema.json").read_text(encoding="utf-8"))
                att_rel = "tools/marketplace/attachments/fixture.bench.demo-imp-0096.live.primary.json"
                att = json.loads((REPO / att_rel).read_text(encoding="utf-8"))
                import jsonschema as _js
                verrs = sorted(_js.Draft202012Validator(bs).iter_errors(att), key=str)
                checks["schema_imp0096_attachment"] = "OK" if not verrs else "FAIL:" + "; ".join(e.message for e in verrs[:3])
            except Exception as exc:
                checks["schema_imp0096_attachment"] = f"FAIL:{type(exc).__name__}:{exc}"
        # 7 gate (12 conditions + coherence) on CURRENT bytes
        try:
            res, extra = RSG.evaluate_full(doc, repo_root=REPO, verify_filesystem=True)
            d = res.to_dict()
            unsat = [c for c in d["conditions"] if c["outcome"] != "SATISFIED"]
            checks["gate"] = ("OK" if (not unsat and not extra) else
                              f"NOTE:unsat={len(unsat)} coherence={extra[:3]}")
            live["gate_unsat"] = [f"{c['n']}:{c['basis'][:120]}" for c in unsat]
            live["gate_coherence"] = extra
        except Exception as exc:
            checks["gate"] = f"NOTE:gate-error:{type(exc).__name__}:{exc}"
        # 8 program measure as second signal
        rc, tail = run_cmd(f'"{sys.executable}" -B command-center/p2-wave/_measure_one_delivered.py {uid}', timeout=1800)
        marker = "SUCCESS:delivered" in tail
        live["measure"] = {"rc": rc, "success": marker, "tail": tail[-400:]}
        checks["measure"] = "OK" if (rc == 0 and marker) else f"NOTE:measure-rc={rc}:{tail.strip().splitlines()[-1][:160] if tail.strip() else 'empty'}"
        verdict = "PASS-CHECKS" if all(v.startswith(("OK", "CLOSE-CANDIDATE")) for v in checks.values() if isinstance(v, str)) else "FAIL-CHECKS"
        if "CLOSE-CANDIDATE" in checks.values():
            verdict = "CLOSE-CANDIDATE" if verdict == "PASS-CHECKS" else "FAIL-CHECKS"
        report[uid] = {"checks": checks, "verdict": verdict, "live": {k: v for k, v in live.items() if k != "probe_cmds"}}
        ok_all &= verdict != "FAIL-CHECKS"
        print(f"{uid}: {verdict} :: " + " ".join(f"{k}={v[:60]}" for k, v in checks.items()))
    (HERE / "battery_out.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print("ALL-PASS" if ok_all else "SOME-FAIL")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
