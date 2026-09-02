#!/usr/bin/env python3
"""Run shard-14 named probes on Windows to capture fail tails (not G-1 measure)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (HERE / "shard-14.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
WRAPPER = WAVE / "seed-stage" / "g1_python.py"


def cmds_for(uid: str) -> list[str]:
    pdir = WAVE / "probes" / uid
    ret_path = pdir / "SUBAGENT-RETURN.json"
    cmds: list[str] = []
    if ret_path.is_file():
        try:
            ret = json.loads(ret_path.read_text(encoding="utf-8"))
        except Exception:
            ret = {}
        if isinstance(ret, dict):
            for key in ("named_probes", "probes"):
                for item in ret.get(key) or []:
                    if isinstance(item, dict) and isinstance(item.get("command"), str):
                        cmd = item["command"].strip()
                        if cmd and cmd not in cmds:
                            cmds.append(cmd)
    if len(cmds) >= 1:
        return cmds
    p1 = sorted(pdir.glob("probe1*.py"))
    p2 = sorted(pdir.glob("probe2*.py"))

    def pick(paths: list[Path]) -> Path | None:
        named = [p for p in paths if p.name not in {"probe1.py", "probe2.py"}]
        if named:
            return named[0]
        return paths[0] if paths else None

    a, b = pick(p1), pick(p2)
    out = []
    if a:
        out.append(f"python3 -B {a.relative_to(REPO).as_posix()}")
    if b:
        out.append(f"python3 -B {b.relative_to(REPO).as_posix()}")
    return out


def strip_unix_env(cmd: str) -> str:
    # named_probes use `VAR=val python3 ...`; cmd.exe treats VAR as a command.
    parts = cmd.split()
    i = 0
    while i < len(parts) and "=" in parts[i] and not parts[i].startswith("-"):
        key, _, val = parts[i].partition("=")
        if key.isidentifier():
            i += 1
            continue
        break
    return " ".join(parts[i:])


def run_cmd(cmd: str) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    py_path = os.pathsep.join(
        [
            str(WAVE / "seed-stage"),
            str(REPO),
            str(REPO / "tools"),
            str(REPO / "tools" / "measure-guard"),
            str(REPO / "platform" / "lib"),
            str(REPO / "tools" / "agentspec"),
            env.get("PYTHONPATH", ""),
        ]
    )
    env["PYTHONPATH"] = py_path
    cmd = strip_unix_env(cmd)
    if WRAPPER.is_file() and "python3" in cmd:
        cmd = cmd.replace("python3", f'"{sys.executable}" "{WRAPPER.as_posix()}"', 1)
    try:
        p = subprocess.run(
            cmd,
            cwd=str(REPO),
            shell=True,
            capture_output=True,
            text=True,
            timeout=12,
            env=env,
        )
        text = ((p.stdout or "") + (p.stderr or "")).strip()
        return {"rc": p.returncode, "tail": "\n".join(text.splitlines()[-16:])}
    except subprocess.TimeoutExpired:
        return {"rc": 124, "tail": "TIMEOUT"}


def main() -> None:
    only = sys.argv[1:]
    ids = only or IDS
    dest = HERE / "_shard14_win_probes.jsonl"
    done: set[str] = set()
    rows = []
    if dest.is_file() and not only:
        for line in dest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                prev = json.loads(line)
            except json.JSONDecodeError:
                continue
            uid = prev.get("id")
            if uid:
                done.add(uid)
                rows.append(prev)
    for uid in ids:
        if uid in done:
            print(f"SKIP {uid} already in jsonl")
            continue
        cmds = cmds_for(uid)
        item = {"id": uid, "cmds": cmds, "probes": []}
        ok = True
        if not cmds:
            ok = False
            item["probes"].append({"cmd": "", "rc": 2, "tail": "named-probes-absent"})
        for cmd in cmds:
            r = run_cmd(cmd)
            item["probes"].append({"cmd": cmd, **r})
            if r["rc"] != 0:
                ok = False
        item["ok"] = ok
        rows.append(item)
        mark = "OK" if ok else "FAIL"
        print(f"{mark} {uid} ncmds={len(cmds)}")
        if not ok:
            for pr in item["probes"]:
                if pr["rc"] != 0:
                    print(f"  rc={pr['rc']} {pr['cmd'][-90:]}")
                    for ln in (pr["tail"] or "").splitlines()[-8:]:
                        print("   ", ln)
        dest.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    dest.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    ok_n = sum(1 for r in rows if r["ok"])
    print(f"wrote {dest} attempted={len(rows)} ok={ok_n} fail={len(rows)-ok_n}")


if __name__ == "__main__":
    main()
