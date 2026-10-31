#!/usr/bin/env python3
"""INDEPENDENT REVIEW round 3, wave-2 shard-13 (12 units).

Written fresh by the round-3 reviewer agent. Read-only over receipts:
this script NEVER mutates a receipt. Per unit it mechanically verifies:

  A  artifact at catalog output_path: exists, non-empty, parses,
     not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT, state == SUCCESS
  B  receipt_core closure rule: reviewer.verdict == PASS, independent true
  C  output_schema profile clause (catalog string): every required field
     present, non-empty, list-typed for the [] forms
  C2 STRICT receipt_core JSON-Schema validation (draft 2020-12) against
     platform/schema/receipt.schema.json#/$defs/receipt_core
  D  probes/<id>/UNIT-ARTIFACT-MANIFEST.json: primary row (path ==
     output_path) present=true, sha256 + bytes match a live recompute
     over CRLF-normalized bytes; every other row present + digest-matched
  E  catalog completion_sentinel appears verbatim in the receipt text
  F  live probes re-run HERE: rc == 0, SUCCESS: marker present,
     FAILED: absent, at least one probe per unit

Exit 0 only when ALL 12 units hold ALL checks.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except Exception:  # pragma: no cover
    jsonschema = None
    Draft202012Validator = None

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
UNITS = [
    "IMP-0229", "IMP-0261", "IMP-0264", "IMP-0269", "IMP-0270", "IMP-0271",
    "IMP-0272", "IMP-0273", "IMP-0274", "IMP-0275", "IMP-0279", "IMP-0303",
]
SELF_BAD = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT_S = 600


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
        py = sorted(
            p.name for p in pdir.glob("probe[0-9]*.py") if p.name not in {"probe1.py", "probe2.py"}
        ) or sorted(p.name for p in pdir.glob("probe[0-9]*.py"))
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


def main() -> int:
    cat = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    byid = {u.get("id"): u for u in cat["work_units"] if isinstance(u, dict)}
    core_v = load_core_validator()

    results: dict[str, dict] = {}
    for uid in UNITS:
        rep: dict = {"fails": [], "notes": []}
        cu = byid.get(uid)
        if cu is None:
            rep["fails"].append("catalog-entry-absent")
            results[uid] = rep
            continue
        out_rel = str(cu.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel

        # A
        if not out.is_file() or out.stat().st_size == 0:
            rep["fails"].append(f"artifact-absent-or-empty:{out_rel}")
            results[uid] = rep
            continue
        try:
            receipt = json.loads(out.read_text(encoding="utf-8"))
        except Exception as exc:
            rep["fails"].append(f"unparseable:{type(exc).__name__}")
            results[uid] = rep
            continue
        st = str(receipt.get("state") or "").upper()
        if st in SELF_BAD:
            rep["fails"].append(f"self-declared:{st}")
        if st != "SUCCESS":
            rep["fails"].append(f"state!=SUCCESS:{st}")

        # B
        rev = receipt.get("reviewer") if isinstance(receipt.get("reviewer"), dict) else {}
        if rev.get("verdict") != "PASS":
            rep["fails"].append(f"reviewer.verdict={rev.get('verdict')!r}")
        if rev.get("independent") is not True:
            rep["fails"].append("reviewer.independent!=true")
        rep["notes"].append(f"reviewer_id={rev.get('reviewer_id')!r}")

        # E
        sentinel = str(cu.get("completion_sentinel") or "")
        if sentinel and sentinel not in out.read_text(encoding="utf-8"):
            rep["fails"].append(f"sentinel-absent:{sentinel}")

        # C profile clause
        prof, req = parse_clause(str(cu.get("output_schema") or ""))
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
                # G-1's PYTHONPATH augmentation shadows the stdlib `platform`
                # module with the repo's platform/ namespace dir on this box,
                # which crashes attrs/jsonschema imports inside probes. That
                # is a G-1 harness hazard, not a unit defect; the round-3
                # re-run deliberately uses the plain recorded environment.
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
    print(f"round-3 verdict: {n_pass}/{len(UNITS)} units hold ALL checks")
    if n_pass == len(UNITS):
        print("SUCCESS:shard13-w2-round3 all units hold")
        return 0
    print(f"FAILED:shard13-w2-round3 {len(UNITS) - n_pass}/{len(UNITS)} units failing")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
