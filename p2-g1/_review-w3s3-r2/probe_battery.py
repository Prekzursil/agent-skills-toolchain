#!/usr/bin/env python3
"""Wave-3 shard-3 reviewer probe battery.

For each unit, TWO mechanically distinct transports:
  T1 (mine, direct): each named probe from probes/<uid>/SUBAGENT-RETURN.json,
     run as [sys.executable, "-B", script] with cwd=REPO, PYTHONDONTWRITEBYTECODE=1,
     per-probe timeout 2700s. rc==0 required; terminal marker recorded.
  T2 (program): command-center/p2-wave/_measure_one_delivered.py <uid>, its own
     Windows env adaptation + g1_python wrapper. rc==0 + "SUCCESS:delivered" required.

Progress is written incrementally to <out>. Usage:
  python probe_battery.py <out.json> <UID> [<UID> ...]
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
PROBES = REPO / "command-center" / "p2-wave" / "probes"
MEASURE = REPO / "command-center" / "p2-wave" / "_measure_one_delivered.py"
TIMEOUT = 2700


def load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return e


def probe_commands(uid: str) -> list[str]:
    """Same selection logic as the program's measure: named_probes first, then
    probe1*/probe2* discovery, then run_probes.py. Returns repo-relative commands."""
    ret = load(PROBES / uid / "SUBAGENT-RETURN.json")
    cmds: list[str] = []
    if isinstance(ret, dict):
        for item in ret.get("named_probes") or []:
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                c = item["command"].strip()
                if c:
                    cmds.append(c)
        for item in ret.get("probes") or []:
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                c = item["command"].strip()
                if c and c not in cmds:
                    cmds.append(c)
    if len(cmds) >= 2:
        return cmds
    p1 = sorted((PROBES / uid).glob("probe1*.py"))
    p2 = sorted((PROBES / uid).glob("probe2*.py"))

    def pick(paths):
        named = [p for p in paths if p.name not in {"probe1.py", "probe2.py"}]
        if named:
            return named[0]
        return paths[0] if paths else None

    a, b = pick(p1), pick(p2)
    if a and b:
        return [
            "PYTHONDONTWRITEBYTECODE=1 python3 -B %s" % a.relative_to(REPO).as_posix(),
            "PYTHONDONTWRITEBYTECODE=1 python3 -B %s" % b.relative_to(REPO).as_posix(),
        ]
    run = PROBES / uid / "run_probes.py"
    if run.is_file():
        return ["PYTHONDONTWRITEBYTECODE=1 python3 -B %s" % run.relative_to(REPO).as_posix()]
    return cmds


def direct_run(script_rel: str) -> tuple[int, float, str]:
    """T1: direct interpreter subprocess, no shell, no wrapper."""
    p = REPO / script_rel
    if not p.is_file():
        return 127, 0.0, "probe script absent: %s" % script_rel
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    t0 = time.monotonic()
    try:
        r = subprocess.run(
            [sys.executable, "-B", str(p)],
            capture_output=True, text=True, timeout=TIMEOUT,
            cwd=str(REPO), env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, time.monotonic() - t0, "TIMEOUT"
    dt = time.monotonic() - t0
    return r.returncode, dt, ((r.stdout or "") + (r.stderr or "")).strip()


def measure_run(uid: str) -> tuple[int, float, str]:
    """T2: the program's own delivery measure."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    t0 = time.monotonic()
    try:
        r = subprocess.run(
            [sys.executable, "-B", str(MEASURE), uid],
            capture_output=True, text=True, timeout=TIMEOUT + 300,
            cwd=str(REPO), env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, time.monotonic() - t0, "TIMEOUT"
    dt = time.monotonic() - t0
    return r.returncode, dt, ((r.stdout or "") + (r.stderr or "")).strip()


def strip_env_prefix(cmd: str) -> str:
    parts = cmd.split()
    while parts and "=" in parts[0].split("=", 1)[0] and parts[0].split("=", 1)[0].isidentifier():
        parts = parts[1:]
    return parts


def main() -> int:
    out_path = Path(sys.argv[1])
    units = sys.argv[2:]
    results: dict = {}
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            results = {}

    def flush():
        out_path.write_text(json.dumps(results, indent=1, ensure_ascii=False),
                            encoding="utf-8", newline="\n")

    for uid in units:
        entry: dict = {"unit_id": uid}
        cmds = probe_commands(uid)
        entry["commands"] = cmds
        t1 = []
        for c in cmds:
            parts = strip_env_prefix(c)
            # last token list: [python3, -B, script]; use sys.executable
            if len(parts) >= 3 and parts[-2] == "-B":
                script = parts[-1]
            elif len(parts) == 1 and parts[0].endswith(".py"):
                script = parts[0]
            else:
                t1.append({"cmd": c, "rc": 126, "sec": 0.0,
                           "tail": "unparseable command: %s" % c})
                continue
            rc, dt, tail = direct_run(script)
            t1.append({"cmd": c, "rc": rc, "sec": round(dt, 1),
                       "tail": tail[-1200:]})
        entry["T1_direct_probes"] = t1
        entry["T1_all_exit0"] = bool(t1) and all(x["rc"] == 0 for x in t1)
        entry["T1_markers"] = [
            ("SUCCESS:" if "SUCCESS:" in x["tail"] else
             "FAILED:" if "FAILED:" in x["tail"] else "no-marker")
            for x in t1]
        rc, dt, tail = measure_run(uid)
        entry["T2_measure"] = {"rc": rc, "sec": round(dt, 1), "tail": tail[-1500:]}
        entry["T2_delivered"] = (rc == 0 and "SUCCESS:delivered" in tail)
        results[uid] = entry
        flush()
        print(uid, "T1_all_exit0=%s T2_delivered=%s" % (
            entry["T1_all_exit0"], entry["T2_delivered"]), flush=True)
    ok = bool(results) and all(
        v.get("T1_all_exit0") and v.get("T2_delivered") for v in results.values())
    print(("SUCCESS:probe battery %d units all green" if ok else
           "FAILED:probe battery has red units") % len(results), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
