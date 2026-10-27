#!/usr/bin/env python3
"""IMP-0478 probe2: documentation-command-verbatim (resume 2026-10-25).

Executes every coverage-table next_command VERBATIM and requires exit 0 for
each mapped class. Planted control: a known non-running command must exit
non-zero (proving this harness detects a failing command rather than passing
everything).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import error_catalog  # noqa: E402


def fail(msg):
    print("FAILED:IMP-0478-probe2 " + str(msg))
    return 1


def _split_env_prefix(cmd):
    """cmd.exe cannot run "VAR=value command" - hoist prefixes into env (measure-style)."""
    import re
    env = os.environ.copy()
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip(chr(34)).strip(chr(39))
        cmd = cmd[m.end():]
    return cmd, env


def main() -> int:
    results = []
    for row in error_catalog._coverage_rows():
        cmd, env = _split_env_prefix(row["next_command"])
        p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True, text=True, timeout=300, env=env)
        tail = ((p.stdout or "") + (p.stderr or "")).strip()
        results.append({
            "command": cmd,
            "exit_code": p.returncode,
            "message_id": row["message_id"],
            "ok": p.returncode == 0,
            "output_tail": tail[-200:],
        })
    planted = subprocess.run('python3 -c "raise SystemExit(7)"', shell=True, capture_output=True)
    payload = {
        "probe": "probe2-doc-commands",
        "commands_executed": len(results),
        "commands_ok": sum(1 for r in results if r["ok"]),
        "failed_classes": [r["message_id"] for r in results if not r["ok"]],
        "planted_control_fires": planted.returncode == 7,
        "planted_exit_code": planted.returncode,
        "planted_non_running_command": 'python3 -c "raise SystemExit(7)"',
        "results": results,
        "pass": all(r["ok"] for r in results) and planted.returncode == 7,
    }
    print(json.dumps(payload, indent=1)[:2000])
    if not payload["planted_control_fires"]:
        return fail("planted-control-did-not-fire")
    if payload["commands_executed"] != 8 or payload["commands_ok"] != 8:
        return fail("verbatim-commands-failed:" + json.dumps(payload["failed_classes"]))
    if not payload["pass"]:
        return fail("pass-false")
    receipt = json.loads((REPO / "command-center/receipts/IMP-0478.json").read_text(encoding="utf-8"))
    st = str(receipt.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail("self-declared:" + st)
    print("SUCCESS:IMP-0478-probe2 doc-commands")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
