#!/usr/bin/env python3
"""Windows-side named-probe runner for shard-07 (diagnosis only, not G-1)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
IDS = [
    ln.strip()
    for ln in (HERE / "shard-07.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
OUT = HERE / "_shard07_win_probes.jsonl"


def cmds_for(uid: str) -> list[str]:
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    ret_path = pdir / "SUBAGENT-RETURN.json"
    cmds: list[str] = []
    if ret_path.is_file():
        try:
            ret = json.loads(ret_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            ret = {}
        if isinstance(ret, dict):
            for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
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
        out.append(f"python -B {a.relative_to(REPO).as_posix()}")
    if b:
        out.append(f"python -B {b.relative_to(REPO).as_posix()}")
    return out


def run_one(uid: str) -> dict:
    cmds = cmds_for(uid)
    rec = {"id": uid, "cmds": cmds, "ok": False, "fails": []}
    if not cmds:
        rec["fails"].append("named-probes-absent")
        return rec
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(REPO / "command-center" / "p2-wave" / "seed-stage"),
            str(REPO),
            str(REPO / "tools"),
            str(REPO / "tools" / "measure-guard"),
            str(REPO / "platform" / "lib"),
            str(REPO / "tools" / "agentspec"),
            env.get("PYTHONPATH") or "",
        ]
    )
    all_ok = True
    tails = []
    for i, cmd in enumerate(cmds, 1):
        # Replace python3 with current interpreter for Windows diagnosis.
        wcmd = cmd.replace("python3", sys.executable).replace(
            "PYTHONDONTWRITEBYTECODE=1 ", ""
        )
        try:
            p = subprocess.run(
                wcmd,
                cwd=str(REPO),
                shell=True,
                capture_output=True,
                text=True,
                timeout=90,
                env=env,
            )
            text = ((p.stdout or "") + (p.stderr or "")).strip()
            rc = p.returncode
        except subprocess.TimeoutExpired:
            text = "TIMEOUT"
            rc = 124
        last = [ln for ln in text.splitlines() if ln.strip()][-1:] or [""]
        tails.append({"i": i, "rc": rc, "last": last[0][:240], "tail": text[-800:]})
        if rc != 0:
            all_ok = False
            rec["fails"].append(last[0][:240] or f"probe-exit:{rc}")
            break
    rec["ok"] = all_ok
    rec["probes"] = tails
    return rec


def main() -> None:
    done = set()
    if OUT.is_file():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                if rec.get("id"):
                    done.add(rec["id"])
    with OUT.open("a", encoding="utf-8") as fh:
        for uid in IDS:
            if uid in done:
                continue
            rec = run_one(uid)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            print(uid, "OK" if rec["ok"] else "FAIL", rec.get("fails")[:1], flush=True)
    print("DONE")


if __name__ == "__main__":
    main()
