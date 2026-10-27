#!/usr/bin/env python3
"""INDEPENDENT REVIEWER wave-3 shard-13 (12 units) - read-only verification.

Written fresh by the wave-3 shard-13 reviewer agent (never a builder of these
units). Per unit, mechanically verifies:

  A  artifact at catalog output_path: exists, non-empty, parses as JSON,
     not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT for a content reason
     (a BLOCKED carrying failure.classification "reviewer-absent" is the
     expected builder terminal and is closable by this reviewer)
  B  receipt closure claim: reviewer.verdict == PASS, independent is true
  E  catalog completion_sentinel appears verbatim in the receipt text
  C  output_schema profile clause (catalog string): every required field
     present, non-empty, list-typed for the [] forms
  C2 STRICT receipt_core JSON-Schema validation (draft 2020-12) against
     platform/schema/receipt.schema.json#/$defs/receipt_core
  D  probes/<id>/UNIT-ARTIFACT-MANIFEST.json: primary row (path ==
     output_path) present=true, sha256 + bytes match a live recompute
     over CRLF-normalized bytes; every other row present + digest-matched
  F  live probes re-run HERE: rc == 0, SUCCESS: marker present,
     FAILED: absent, at least one probe per unit

Exit 0 only when ALL 12 units hold ALL checks. Read-only: never mutates a
receipt or manifest. Verdicts go to _reviewer-w3s13/verify_out.json.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except Exception:  # pragma: no cover
    jsonschema = None
    Draft202012Validator = None

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
ENTRIES = REPO / "_shard13-w3-entries.json"
OUT_JSON = REPO / "_reviewer-w3s13" / "verify_out.json"
SELF_BAD = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT_S = 600
UNITS = [
    "IMP-0321", "IMP-0329", "IMP-0355", "IMP-0360", "IMP-0371", "IMP-0374",
    "IMP-0390", "IMP-0402", "IMP-0409", "IMP-0415", "IMP-0421", "IMP-0423",
]


def digest(p: Path) -> tuple[str, int]:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def parse_clause(schema_str: str) -> tuple[str | None, list[str]]:
    prof = re.search(r"profile=([\w.-]+)", schema_str or "")
    req: list[str] = []
    rm = re.search(r"required:\s*([^)]+)\)", schema_str or "")
    if rm:
        req = [t.strip() for t in rm.group(1).split(",") if t.strip()]
    return (prof.group(1) if prof else None), req


def check_clause(receipt: dict, req: list[str]) -> list[str]:
    bad: list[str] = []
    for f in req:
        is_list = f.endswith("[]")
        name = f[:-2] if is_list else f
        if name not in receipt:
            bad.append(f"{name}:absent")
            continue
        v = receipt[name]
        if v is None or v == "" or v == []:
            bad.append(f"{name}:empty")
        elif is_list and not isinstance(v, list):
            bad.append(f"{name}:not-list")
    return bad


def load_core_validator():
    if Draft202012Validator is None:
        return None
    sch = json.loads(
        (REPO / "platform" / "schema" / "receipt.schema.json").read_text(encoding="utf-8")
    )
    core = dict(sch["$defs"]["receipt_core"])
    core["$defs"] = sch["$defs"]
    Draft202012Validator.check_schema(core)
    return Draft202012Validator(core)


def probe_cmds(uid: str, pdir: Path) -> list[str]:
    cmds: list[str] = []
    ret_path = pdir / "SUBAGENT-RETURN.json"
    if ret_path.is_file():
        try:
            ret = json.loads(ret_path.read_text(encoding="utf-8"))
        except Exception:
            ret = {}
        for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                c = item["command"].strip()
                if c and c not in cmds:
                    cmds.append(c)
    if len(cmds) < 2:
        py = sorted(p.name for p in pdir.glob("probe[0-9]*.py"))
        for name in py:
            c = f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/{uid}/{name}"
            if c not in cmds:
                cmds.append(c)
    return cmds


def winify(cmd: str, env: dict) -> str:
    # move POSIX VAR=value prefixes into env (same repair as G-1, 2026-10-24)
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            return cmd
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]


def verify_unit(uid: str, cu: dict, core_v) -> dict:
    rep: dict = {"fails": [], "notes": [], "closable": False}
    out_rel = str(cu.get("output_path") or "").replace("\\", "/")
    out = REPO / out_rel
    rep["output_path"] = out_rel

    # A
    if not out.is_file() or out.stat().st_size == 0:
        rep["fails"].append(f"artifact-absent-or-empty:{out_rel}")
        return rep
    raw_text = out.read_text(encoding="utf-8")
    try:
        receipt = json.loads(raw_text)
    except Exception as exc:
        rep["fails"].append(f"unparseable:{type(exc).__name__}")
        return rep
    st = str(receipt.get("state") or "").upper()
    fcls = ((receipt.get("failure") or {}).get("classification") or [])
    if st in SELF_BAD:
        if st == "BLOCKED" and "reviewer-absent" in [str(x) for x in fcls]:
            rep["closable"] = True
            rep["notes"].append("state=BLOCKED/reviewer-absent (closable by reviewer)")
        else:
            rep["fails"].append(f"self-declared:{st}")
    if st != "SUCCESS" and not rep["closable"]:
        rep["fails"].append(f"state!=SUCCESS:{st}")

    # B (current closure claim; this reviewer re-issues it after A-F all hold)
    rev = receipt.get("reviewer") if isinstance(receipt.get("reviewer"), dict) else {}
    rep["claimed_reviewer_id"] = rev.get("reviewer_id")
    if rev.get("verdict") != "PASS":
        rep["fails"].append(f"reviewer.verdict={rev.get('verdict')!r}")
    if rev.get("independent") is not True:
        rep["fails"].append("reviewer.independent!=true")
    rep["notes"].append(f"claimed_reviewer_id={rev.get('reviewer_id')!r}")

    # E
    sentinel = str(cu.get("completion_sentinel") or "")
    if sentinel and sentinel not in raw_text:
        rep["fails"].append(f"sentinel-absent:{sentinel}")

    # C profile clause
    prof, req = parse_clause(str(cu.get("output_schema") or ""))
    rep["profile"] = prof
    rep["notes"].append(f"profile={prof} required={len(req)}")
    rep["fails"].extend("clause:" + b for b in check_clause(receipt, req))

    # C2 strict receipt_core
    if core_v is not None:
        errs = sorted(core_v.iter_errors(receipt), key=lambda e: list(e.absolute_path))
        rep["notes"].append(f"strict-errors={len(errs)}")
        for e in errs[:6]:
            where = "/".join(str(x) for x in e.absolute_path) or "<root>"
            rep["fails"].append(f"schema:{where}::{e.message[:180]}")
        if len(errs) > 6:
            rep["fails"].append(f"schema:...{len(errs) - 6} more")
    else:
        rep["notes"].append("jsonschema-unavailable")

    # D manifest
    man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    named_rows: list[str] = []
    if not man_path.is_file():
        rep["fails"].append("manifest-absent")
    else:
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
        except Exception as exc:
            man = None
            rep["fails"].append(f"manifest-unparseable:{type(exc).__name__}")
        if isinstance(man, dict):
            rows = [a for a in (man.get("artifacts") or []) if isinstance(a, dict)]
            prim = [a for a in rows if str(a.get("path") or "").replace("\\", "/") == out_rel]
            if not prim:
                rep["fails"].append("manifest-primary-row-absent")
            else:
                live_sha, live_n = digest(out)
                p0 = prim[0]
                if p0.get("present") is not True:
                    rep["fails"].append("manifest-primary-present!=true")
                if str(p0.get("sha256") or "") != live_sha:
                    rep["fails"].append(
                        f"manifest-primary-sha-mismatch man={str(p0.get('sha256'))[:12]} live={live_sha[:12]}"
                    )
                if p0.get("bytes") != live_n:
                    rep["fails"].append(f"manifest-primary-bytes man={p0.get('bytes')} live={live_n}")
            for a in rows:
                rel = str(a.get("path") or "").replace("\\", "/")
                if rel == out_rel:
                    continue
                if a.get("role") == "named-probe" and rel.endswith(".py"):
                    named_rows.append(rel)
                fp = REPO / rel
                if not fp.is_file():
                    rep["fails"].append(f"manifest-row-absent:{rel}")
                    continue
                s2, n2 = digest(fp)
                if s2 != str(a.get("sha256") or "") or n2 != a.get("bytes"):
                    rep["fails"].append(
                        f"manifest-row-digest:{rel} man={str(a.get('sha256'))[:12]}/{a.get('bytes')} live={s2[:12]}/{n2}"
                    )
            rep["notes"].append(f"manifest-rows={len(rows)}")

    # F live probes
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    cmds = probe_cmds(uid, pdir)
    extra = [
        f"PYTHONDONTWRITEBYTECODE=1 python3 -B {r}"
        for r in named_rows
        if not any(r in c for c in cmds)
    ]
    cmds += extra
    if not cmds:
        rep["fails"].append("no-live-probes-found")
    else:
        ok_runs = 0
        for cmd in cmds:
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            # Recorded probe commands are run AS RECORDED (plain env):
            # a PYTHONPATH carrying the repo root shadows the stdlib
            # `platform` module with the repo's platform/ namespace dir,
            # crashing attrs/jsonschema imports inside probes. That is a
            # harness hazard, not a unit defect; re-run uses plain env.
            env.pop("PYTHONPATH", None)
            env.pop("AST_INTEGRATE_ROOT", None)
            cmd = winify(cmd, env)
            if " -B " in cmd:
                argv = [sys.executable, "-B"] + cmd.split(" ")[2:]
            else:
                argv = [sys.executable] + cmd.split(" ")[1:]
            try:
                cp = subprocess.run(
                    argv, cwd=str(REPO), env=env, capture_output=True, text=True,
                    timeout=PROBE_TIMEOUT_S, encoding="utf-8", errors="replace",
                )
                rc, so, se = cp.returncode, cp.stdout or "", cp.stderr or ""
            except subprocess.TimeoutExpired:
                rep["fails"].append(f"probe-timeout:{Path(argv[-1]).name}")
                continue
            pname = Path(argv[-1]).name
            if rc != 0:
                rep["fails"].append(f"probe-rc:{pname}={rc}")
            if "SUCCESS:" not in so:
                rep["fails"].append(f"probe-no-success-marker:{pname}")
            if "FAILED:" in so or "FAILED:" in se:
                rep["fails"].append(f"probe-failed-marker:{pname}")
            if rc == 0 and "SUCCESS:" in so and "FAILED:" not in (so + se):
                ok_runs += 1
        rep["notes"].append(f"probes-ok={ok_runs}/{len(cmds)}")

    return rep


def main() -> int:
    entries = json.loads(ENTRIES.read_text(encoding="utf-8"))
    core_v = load_core_validator()
    results: dict[str, dict] = {}
    for uid in UNITS:
        cu = entries.get(uid)
        if cu is None:
            results[uid] = {"fails": ["catalog-entry-absent"], "notes": []}
            continue
        t0 = time.time()
        rep = verify_unit(uid, cu, core_v)
        rep["seconds"] = round(time.time() - t0, 1)
        results[uid] = rep

    print("=" * 100)
    n_pass = 0
    for uid in UNITS:
        rep = results.get(uid, {"fails": ["no-result"], "notes": []})
        if rep["fails"]:
            print(f"{uid} FAIL")
            for f in rep["fails"]:
                print(f"    - {f}")
            for nline in rep["notes"]:
                print(f"    # {nline}")
        else:
            n_pass += 1
            print(f"{uid} PASS  ({'; '.join(rep['notes'])})")
    print("=" * 100)
    print(f"TOTAL: {n_pass}/{len(UNITS)} PASS")
    OUT_JSON.write_text(
        json.dumps({"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "units": UNITS, "results": results}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0 if n_pass == len(UNITS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
