#!/usr/bin/env python3
"""G-1 per-unit delivery measure.

SUCCESS:delivered only when, for THIS unit:
  * the catalog output_path exists, is non-empty, parses, and is not self-declared BLOCKED
  * live named probes re-run and exit 0
  * probes/<id>/UNIT-ARTIFACT-MANIFEST.json has a row whose sha256 matches the live artifact
cloud ok=true is not consulted.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
UID_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")


def fail(uid: str, reason: str, code: int = 1) -> int:
    print(f"FAILED:delivered {uid} {reason}")
    return code


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return exc


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def catalog_unit(uid: str):
    data = load_json(CATALOG)
    if not isinstance(data, dict):
        return None
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    return None


def probe_commands(uid: str, ret: dict | None, probe_dir: Path) -> list[str]:
    cmds: list[str] = []
    if isinstance(ret, dict):
        for item in ret.get("named_probes") or []:
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                cmds.append(item["command"].strip())
        for item in ret.get("probes") or []:
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                cmd = item["command"].strip()
                if cmd and cmd not in cmds:
                    cmds.append(cmd)
    if len(cmds) >= 2:
        return cmds
    p1 = sorted(probe_dir.glob("probe1*.py"))
    p2 = sorted(probe_dir.glob("probe2*.py"))
    # Prefer the long-named scripts over thin aliases when both exist.
    def pick(paths: list[Path]) -> Path | None:
        named = [p for p in paths if p.name not in {"probe1.py", "probe2.py"}]
        if named:
            return named[0]
        return paths[0] if paths else None

    a, b = pick(p1), pick(p2)
    if a and b:
        return [
            f"PYTHONDONTWRITEBYTECODE=1 python3 -B {a.relative_to(REPO).as_posix()}",
            f"PYTHONDONTWRITEBYTECODE=1 python3 -B {b.relative_to(REPO).as_posix()}",
        ]
    run = probe_dir / "run_probes.py"
    if run.is_file():
        return [
            f"PYTHONDONTWRITEBYTECODE=1 python3 -B {run.relative_to(REPO).as_posix()}"
        ]
    return cmds


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    hook_dir = str(REPO / "command-center" / "p2-wave" / "seed-stage")
    py_path = os.pathsep.join(
        [
            hook_dir,
            str(REPO),
            str(REPO / "tools"),
            str(REPO / "tools" / "measure-guard"),
            str(REPO / "platform" / "lib"),
            str(REPO / "tools" / "agentspec"),
            env.get("PYTHONPATH", ""),
        ]
    )
    env["PYTHONPATH"] = py_path
    wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
    if wrapper.is_file() and "python3" in cmd:
        cmd = cmd.replace("python3", f"{sys.executable} {wrapper.as_posix()}", 1)
    try:
        p = subprocess.run(
            cmd,
            cwd=str(REPO),
            shell=True,
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text[-4000:]


def main() -> int:
    if len(sys.argv) < 2 or not UID_RE.match(sys.argv[1]):
        print("FAILED:delivered usage _measure_one_delivered.py <UNIT-ID>")
        return 2
    uid = sys.argv[1]
    unit = catalog_unit(uid)
    if unit is None:
        return fail(uid, "catalog-missing", 2)
    probe_dir = PROBES / uid
    if not probe_dir.is_dir():
        return fail(uid, "predicate:absent")
    out_rel = str(unit.get("output_path") or "").replace("\\", "/")
    if not out_rel:
        return fail(uid, "predicate:absent")
    out = REPO / out_rel
    if not out.is_file() or out.stat().st_size <= 0:
        return fail(uid, "predicate:absent")
    try:
        text = out.read_text(encoding="utf-8")
        doc = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return fail(uid, f"unparseable:{type(exc).__name__}")
    if isinstance(doc, dict):
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            return fail(uid, f"self-declared:{st}")
        sentinel = str(unit.get("completion_sentinel") or "")
        if sentinel and sentinel not in text:
            return fail(uid, "sentinel-absent")
    ret_path = probe_dir / "SUBAGENT-RETURN.json"
    man_path = probe_dir / "UNIT-ARTIFACT-MANIFEST.json"
    if not ret_path.is_file() or not man_path.is_file():
        return fail(uid, "predicate:absent")
    ret = load_json(ret_path)
    if not isinstance(ret, dict):
        return fail(uid, "return-unparseable")
    st_ret = str(ret.get("status") or ret.get("state") or "").upper()
    if st_ret in NOT_DELIVERING:
        return fail(uid, f"return:{st_ret}")
    cmds = probe_commands(uid, ret, probe_dir)
    if len(cmds) < 1:
        return fail(uid, "named-probes-absent")
    for i, cmd in enumerate(cmds, 1):
        code, tail = run_cmd(cmd)
        print(f"probe[{i}] rc={code} cmd={cmd}")
        if tail:
            for line in tail.splitlines()[-8:]:
                print(f"  {line}")
        if code != 0:
            return fail(uid, f"probe-exit:{code}")
    man = load_json(man_path)
    if not isinstance(man, dict):
        return fail(uid, "per-unit-manifest-unparseable")
    rows = [
        a
        for a in (man.get("artifacts") or [])
        if isinstance(a, dict) and a.get("unit_id") == uid
    ]
    if not rows:
        return fail(uid, "per-unit-manifest-row-absent")
    live_sha, live_bytes = digest_file(out)
    matching = [
        a
        for a in rows
        if str(a.get("path") or "").replace("\\", "/") == out_rel
        and str(a.get("sha256") or "") == live_sha
        and a.get("present") is True
    ]
    if not matching:
        return fail(uid, "manifest-sha-mismatch")
    print(f"artifact {out_rel} bytes={live_bytes} sha256={live_sha}")
    print(f"SUCCESS:delivered {uid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
