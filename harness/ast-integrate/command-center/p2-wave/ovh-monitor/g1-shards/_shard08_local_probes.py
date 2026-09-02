#!/usr/bin/env python3
"""Windows-local named-probe smoke for shard-08 (diagnosis only, not G-1)."""
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
    for ln in (HERE / "shard-08.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
PROBES = REPO / "command-center" / "p2-wave" / "probes"
WRAPPER = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
OUT = HERE / "_shard08_local_probes.jsonl"

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
    if len(cmds) >= 1:
        return cmds
    scripts = sorted(pdir.glob("probe*.py"))
    return [str(s) for s in scripts]


def run_one(uid: str, cmd: str) -> dict:
    # extract script path after python3 -B
    script = cmd
    parts = cmd.split()
    for i, p in enumerate(parts):
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
            timeout=90,
            env=env,
        )
        text = ((p.stdout or "") + (p.stderr or "")).strip()
        return {
            "id": uid,
            "cmd": cmd,
            "rc": p.returncode,
            "tail": text.splitlines()[-12:],
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
            for cmd in cmds:
                row = run_one(uid, cmd)
                fh.write(json.dumps(row) + "\n")
                fh.flush()
                status = "OK" if row["rc"] == 0 else "FAIL"
                if row["rc"] != 0:
                    unit_ok = False
                last = row["tail"][-1] if row["tail"] else ""
                print(f"{status}\t{uid}\trc={row['rc']}\t{last[:140]}")
            if unit_ok and cmds:
                ok += 1
            else:
                fail += 1
    print(f"LOCAL-DONE units_ok={ok} units_fail={fail}")


if __name__ == "__main__":
    main()
