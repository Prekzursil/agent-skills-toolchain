#!/usr/bin/env python3
"""Documentation-command probe: execute every recommended next command verbatim.

A command that is merely written in the catalog is not evidence. This probe
runs the exact next_command string from each coverage-table row.

Control: a command that exits non-zero would fail this probe (demonstrated on
a planted `python3 -c "raise SystemExit(7)"` that is NOT in the catalog).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import error_catalog as C  # noqa: E402

PLANTED_BAD = 'python3 -c "raise SystemExit(7)"'


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text[-4000:]


def main() -> int:
    rows = C.coverage_table()
    results = []
    failed = []
    for row in rows:
        cmd = row["next_command"]
        if not cmd:
            failed.append(row["taxonomy_class"])
            results.append(
                {
                    "taxonomy_class": row["taxonomy_class"],
                    "command": cmd,
                    "exit_code": None,
                    "ok": False,
                    "reason": "missing-next-command",
                }
            )
            continue
        code, tail = run_cmd(cmd)
        ok = code == 0 and "WHAT:" in tail and "WHY:" in tail and "NEXT:" in tail
        if not ok:
            failed.append(row["taxonomy_class"])
        results.append(
            {
                "taxonomy_class": row["taxonomy_class"],
                "message_id": row["message_id"],
                "command": cmd,
                "exit_code": code,
                "ok": ok,
                "output_tail": tail[-500:],
            }
        )

    bad_code, _bad_tail = run_cmd(PLANTED_BAD)
    control_fires = bad_code == 7

    payload = {
        "probe": "probe2-doc-commands",
        "unit_id": "IMP-0478",
        "commands_executed": len(results),
        "commands_ok": sum(1 for r in results if r["ok"]),
        "failed_classes": failed,
        "planted_non_running_command": PLANTED_BAD,
        "planted_exit_code": bad_code,
        "planted_control_fires": control_fires,
        "results": results,
        "pass": (not failed) and control_fires and len(results) == len(C.CLOSED_TAXONOMY),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"executed={len(results)} ok={payload['commands_ok']} "
        f"failed={failed} planted_exit={bad_code}"
    )
    if not payload["pass"]:
        print("FAILED:IMP-0478-probe2 recommended command did not run")
        return 1
    print("SUCCESS:IMP-0478-probe2 every recommended next command executed verbatim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
