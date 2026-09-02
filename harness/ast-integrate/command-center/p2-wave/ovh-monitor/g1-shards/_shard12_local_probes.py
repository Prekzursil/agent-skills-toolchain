#!/usr/bin/env python3
"""Windows-local named-probe smoke for shard-12 (diagnosis only, not G-1)."""
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
    for ln in (HERE / "shard-12.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
PROBES = REPO / "command-center" / "p2-wave" / "probes"
WRAPPER = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
OUT = HERE / "_shard12_local_probes.jsonl"

hook_dir = str(REPO / "command-center" / "p2-wave" / "seed-stage")
env = os.environ.copy()
env["PYTHONDONTWRITEBYTECODE"] = "1"
env["AST_INTEGRATE_ROOT"] = str(REPO)
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


def cmds_for(uid: str) -> list[str]:
    pdir = PROBES / uid
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
    if cmds:
        return cmds
    scripts = []
    for globn in ("probe1*.py", "probe2*.py"):
        paths = sorted(pdir.glob(globn))
        named = [p for p in paths if p.name not in {"probe1.py", "probe2.py"}]
        pick = named[0] if named else (paths[0] if paths else None)
        if pick is not None:
            scripts.append(str(pick.relative_to(REPO)).replace("\\", "/"))
    return scripts


def run_one(uid: str, cmd: str) -> dict:
    script = cmd
    parts = cmd.split()
    for p in parts:
        if p.endswith(".py") and "probe" in p.replace("\\", "/"):
            script = p
            break
    py = sys.executable
    argv = [py, "-B", str(WRAPPER), str(REPO / script.replace("/", os.sep))]
    try:
        p = subprocess.run(
            argv,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=70,
            env=env,
        )
        text = ((p.stdout or "") + (p.stderr or "")).strip()
        return {
            "id": uid,
            "cmd": cmd,
            "rc": p.returncode,
            "tail": text.splitlines()[-16:],
        }
    except subprocess.TimeoutExpired:
        return {"id": uid, "cmd": cmd, "rc": 124, "tail": ["TIMEOUT"]}
    except Exception as exc:
        return {"id": uid, "cmd": cmd, "rc": 99, "tail": [f"{type(exc).__name__}:{exc}"]}


def main() -> None:
    if OUT.exists():
        OUT.unlink()
    ok = fail = 0
    with OUT.open("a", encoding="utf-8") as fh:
        for uid in IDS:
            cmds = cmds_for(uid)
            unit_ok = True
            if not cmds:
                row = {"id": uid, "cmd": "", "rc": 2, "tail": ["named-probes-absent"]}
                fh.write(json.dumps(row) + "\n")
                fh.flush()
                print(f"FAIL\t{uid}\trc=2\tnamed-probes-absent")
                fail += 1
                continue
            for cmd in cmds:
                row = run_one(uid, cmd)
                fh.write(json.dumps(row) + "\n")
                fh.flush()
                status = "OK" if row["rc"] == 0 else "FAIL"
                if row["rc"] != 0:
                    unit_ok = False
                last = row["tail"][-1] if row["tail"] else ""
                print(f"{status}\t{uid}\trc={row['rc']}\t{last[:160]}", flush=True)
            if unit_ok:
                ok += 1
            else:
                fail += 1
    print(f"LOCAL-DONE units_ok={ok} units_fail={fail} n={len(IDS)}", flush=True)


if __name__ == "__main__":
    main()
