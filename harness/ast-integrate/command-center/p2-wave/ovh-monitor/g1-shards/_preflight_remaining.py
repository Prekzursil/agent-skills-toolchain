#!/usr/bin/env python3
"""Windows preflight for remaining class-probe-missing IDs."""
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
][12:]
# Optional: argv subset
if len(sys.argv) > 1:
    IDS = [a for a in sys.argv[1:] if a]


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
    parts = cmd.split()
    py = None
    extra = []
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
    tail = ((p.stdout or "") + (p.stderr or "")).strip()[-2000:]
    return p.returncode, tail


def main() -> None:
    rows = []
    for uid in IDS:
        rec = {"id": uid, "probes": []}
        try:
            clist = cmds(uid)
        except Exception as exc:
            rec["error"] = str(exc)
            rec["ok"] = False
            rows.append(rec)
            print(uid, "NO-CMDS", exc)
            continue
        for i, cmd in enumerate(clist, 1):
            try:
                code, tail = run_one(cmd)
            except Exception as exc:
                code, tail = 99, f"{type(exc).__name__}: {exc}"
            rec["probes"].append({"i": i, "rc": code, "cmd": cmd, "tail": tail[-800:]})
            print(f"{uid} probe[{i}] rc={code}")
            if code != 0:
                print(tail[-500:])
        rec["ok"] = bool(rec["probes"]) and all(p["rc"] == 0 for p in rec["probes"])
        rows.append(rec)
    out = WAVE / "ovh-monitor" / "g1-shards" / "_preflight_remaining.json"
    out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print("OK", sum(1 for r in rows if r.get("ok")), "FAIL", sum(1 for r in rows if not r.get("ok")))


if __name__ == "__main__":
    main()
