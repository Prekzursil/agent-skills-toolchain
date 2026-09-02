#!/usr/bin/env python3
"""Run named probes for shard-02 on this tree; capture tails (Windows diagnosis)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "shard-02.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
]
PROBES = WAVE / "probes"
OUT = WAVE / "ovh-monitor" / "g1-shards" / "_shard02_win_probes.jsonl"


def cmds_for(uid: str) -> list[str]:
    probe_dir = PROBES / uid
    ret_path = probe_dir / "SUBAGENT-RETURN.json"
    ret = None
    if ret_path.is_file():
        try:
            ret = json.loads(ret_path.read_text(encoding="utf-8"))
        except Exception:
            ret = None
    cmds: list[str] = []
    if isinstance(ret, dict):
        for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                cmd = item["command"].strip()
                if cmd and cmd not in cmds:
                    cmds.append(cmd)
    if len(cmds) >= 2:
        return cmds[:4]
    p1 = sorted(probe_dir.glob("probe1*.py"))
    p2 = sorted(probe_dir.glob("probe2*.py"))

    def pick(paths: list[Path]) -> Path | None:
        named = [p for p in paths if p.name not in {"probe1.py", "probe2.py"}]
        if named:
            return named[0]
        return paths[0] if paths else None

    a, b = pick(p1), pick(p2)
    out = []
    if a:
        out.append(str(a.relative_to(REPO).as_posix()))
    if b:
        out.append(str(b.relative_to(REPO).as_posix()))
    run = probe_dir / "run_probes.py"
    if not out and run.is_file():
        out.append(str(run.relative_to(REPO).as_posix()))
    return out


def run_one(cmd: str) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    hook_dir = str(REPO / "command-center" / "p2-wave" / "seed-stage")
    env["PYTHONPATH"] = os.pathsep.join(
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
    script = cmd
    extra: list[str] = []
    if "python3" in cmd or cmd.endswith(".py") or "probes" in cmd.replace("\\", "/"):
        parts = cmd.split()
        for i, p in enumerate(parts):
            if p.endswith(".py") and "probes" in p.replace("\\", "/"):
                script = p
                extra = parts[i + 1 :]
                break
    wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
    argv = [sys.executable, "-B", str(wrapper), str(REPO / script), *extra]
    try:
        p = subprocess.run(
            argv,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=75,
            env=env,
        )
        text = ((p.stdout or "") + (p.stderr or "")).strip()
        return {
            "rc": p.returncode,
            "tail": "\n".join(text.splitlines()[-16:]),
            "cmd": script,
        }
    except subprocess.TimeoutExpired:
        return {"rc": 124, "tail": "TIMEOUT", "cmd": script}


def main() -> None:
    if OUT.is_file():
        OUT.unlink()
    ok = 0
    fail = 0
    for uid in IDS:
        cmds = cmds_for(uid)
        rec: dict = {"id": uid, "cmds": cmds, "probes": []}
        if not cmds:
            rec["error"] = "named-probes-absent"
            print(f"{uid} NO-PROBES", flush=True)
            fail += 1
            OUT.open("a", encoding="utf-8", newline="\n").write(json.dumps(rec) + "\n")
            continue
        for cmd in cmds:
            r = run_one(cmd)
            rec["probes"].append(r)
            mark = "OK" if r["rc"] == 0 else f"FAIL:{r['rc']}"
            last = r["tail"].splitlines()[-1] if r["tail"] else ""
            print(f"{uid} {mark} {Path(r['cmd']).name} {last[:160]}", flush=True)
        if rec["probes"] and all(p["rc"] == 0 for p in rec["probes"]):
            ok += 1
        else:
            fail += 1
        OUT.open("a", encoding="utf-8", newline="\n").write(json.dumps(rec) + "\n")
    print(f"DONE ok={ok} fail={fail} attempted={len(IDS)} wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
