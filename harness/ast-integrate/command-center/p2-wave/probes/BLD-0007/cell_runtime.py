"""Shared runtime for generated per-cell probe scripts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from cmd_model import catch_bare_sh  # noqa: E402
from host import cell_available, detect  # noqa: E402


def run_cell(cell_id: str, os_name: str, shell: str) -> dict:
    host = detect()
    ok, detail = cell_available(os_name, shell, host)
    extra: dict = {}
    if cell_id == "windows__cmd.exe":
        # ASSERTION: bare .sh on Windows is caught even when cmd.exe is absent;
        # the model is the cmd.exe cell probe's catching logic.
        caught = catch_bare_sh()
        extra["bare_sh"] = caught
        if not caught["ok"]:
            return {
                "id": cell_id,
                "os": os_name,
                "shell": shell,
                "status": "FAIL",
                "reason": "cmd.exe cell probe did not catch bare .sh invocation",
                "host_os": host["os"],
                "detail": detail,
                **extra,
            }
    if ok:
        status = "RUN"
        reason = f"executed on host os={host['os']} interpreter={detail}"
    else:
        status = "NOT-CHECKED"
        reason = detail
    return {
        "id": cell_id,
        "os": os_name,
        "shell": shell,
        "status": status,
        "reason": reason,
        "host_os": host["os"],
        "host_wsl": host["wsl"],
        "interpreter": detail if ok else None,
        **extra,
    }


def main_cell(cell_id: str, os_name: str, shell: str) -> int:
    row = run_cell(cell_id, os_name, shell)
    print(json.dumps(row, sort_keys=True))
    print(f"SUCCESS:BLD-0007-cell {cell_id} status={row['status']}")
    return 0
