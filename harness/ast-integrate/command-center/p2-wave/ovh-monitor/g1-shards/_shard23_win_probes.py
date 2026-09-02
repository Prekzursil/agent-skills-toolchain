#!/usr/bin/env python3
"""Windows-side named-probe runner for shard-23 (diagnosis only, not G-1)."""
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
    for ln in (HERE / "shard-23.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
OUT = HERE / "_shard23_win_probes.jsonl"


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
    if cmds:
        return cmds
    p1 = sorted(pdir.glob("probe1*.py"))
    p2 = sorted(pdir.glob("probe2*.py"))

    def pick(paths: list[Path]) -> Path | None:
        named = [p for p in paths if p.name not in {"probe1.py", "probe2.py"}]
        if named:
            return named[0]
        return paths[0] if paths else None

    out = []
    a, b = pick(p1), pick(p2)
    if a:
        out.append(f"python -B {a.relative_to(REPO).as_posix()}")
    if b:
        out.append(f"python -B {b.relative_to(REPO).as_posix()}")
    return out


def run_one(uid: str) -> dict:
    cmds = cmds_for(uid)
    rec: dict = {"id": uid, "cmds": cmds, "ok": False, "fails": []}
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
            str(REPO / "command-center"),
            env.get("PYTHONPATH") or "",
        ]
    )
    all_ok = True
    tails = []
    for i, cmd in enumerate(cmds, 1):
        wcmd = cmd.replace("python3", f'"{sys.executable}"').replace(
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
        lines = [ln for ln in text.splitlines() if ln.strip()]
        last = lines[-1][:400] if lines else ""
        tails.append({"i": i, "rc": rc, "last": last, "tail": text[-1800:]})
        if rc != 0:
            all_ok = False
            rec["fails"].append(last or f"probe-exit:{rc}")
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
                print("skip-done", uid)
                continue
            rec = run_one(uid)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            mark = "OK" if rec.get("ok") else "FAIL"
            fail = (rec.get("fails") or ["?"])[0][:220]
            print(mark, uid, fail if mark == "FAIL" else "probes-pass")


if __name__ == "__main__":
    main()
