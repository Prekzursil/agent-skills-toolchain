"""Execute documented commands and compute coverage (IMP-0252)."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

FENCE = re.compile(r"```(\w+)([^\n]*)\n(.*?)```", re.S)


def run_example(path: Path, execute: bool = True) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    commands = []
    marked = 0
    for lang, flags, body in FENCE.findall(text):
        not_exec = "NOT-EXECUTABLE" in flags.upper()
        if not_exec:
            marked += 1
        for line in body.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            commands.append({"command": line, "lang": lang, "not_executable": not_exec})
    claimed = len(commands)
    executed = 0
    broken = []
    rows = []
    for cmd in commands:
        if not execute or cmd["not_executable"]:
            rows.append({**cmd, "executed": False, "exit_code": None})
            continue
        proc = subprocess.run(cmd["command"], shell=True, capture_output=True, text=True)
        executed += 1
        row = {**cmd, "executed": True, "exit_code": proc.returncode}
        rows.append(row)
        if proc.returncode != 0:
            broken.append(row)
    untested = claimed - executed - marked if execute else claimed
    if not execute:
        untested = claimed
        coverage = 0.0
    else:
        denom = claimed - marked
        coverage = (executed - len(broken)) / denom if denom else 1.0
    return {
        "claimed": claimed,
        "executed": executed,
        "untested": untested,
        "broken": broken,
        "commands": rows,
        "coverage": float(coverage),
        "coverage_computed": True,
        "pass_clean": execute and not broken and untested == 0,
        "marked": marked,
        "execute": execute,
    }
