#!/usr/bin/env python3
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
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "class-probe-missing.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
][:12]


def cmds(uid: str) -> list[str]:
    ret = json.loads((WAVE / "probes" / uid / "SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
    out = []
    for item in ret.get("named_probes") or []:
        if isinstance(item, dict) and isinstance(item.get("command"), str):
            out.append(item["command"].strip())
    return out


def run_one(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    env["PYTHONPATH"] = os.pathsep.join(
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
    # Strip the unix wrapper; run with this interpreter.
    parts = cmd.split()
    py = None
    for i, tok in enumerate(parts):
        if tok.endswith(".py") and "probes/" in tok.replace("\\", "/"):
            py = tok
            extra = parts[i + 1 :]
            break
    if py is None:
        return 2, "no-py"
    p = subprocess.run(
        [sys.executable, "-B", str(REPO / py), *extra],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    tail = ((p.stdout or "") + (p.stderr or "")).strip()[-1500:]
    return p.returncode, tail


def main() -> None:
    rows = []
    for uid in IDS:
        rec = {"id": uid, "probes": []}
        for i, cmd in enumerate(cmds(uid), 1):
            code, tail = run_one(cmd)
            rec["probes"].append({"i": i, "rc": code, "cmd": cmd, "tail": tail[-800:]})
            print(f"{uid} probe[{i}] rc={code}")
            if code != 0:
                print(tail[-600:])
        rec["ok"] = all(p["rc"] == 0 for p in rec["probes"])
        rows.append(rec)
    out = WAVE / "ovh-monitor" / "g1-shards" / "_preflight12.json"
    out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print("OK", sum(1 for r in rows if r["ok"]), "FAIL", sum(1 for r in rows if not r["ok"]))


if __name__ == "__main__":
    main()
