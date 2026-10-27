"""TST-0338 coverage-threshold resolver.

Contract (catalog unit TST-0338):
  * locate the project's .coverage-thresholds.json in the project root ONLY -
    a parent-directory thresholds file is a TRAP and must never be inherited;
  * run the enforcement command declared INSIDE that file, in the project
    root, verbatim, and report its exit code without interpreting it as a
    coverage pass;
  * when the file does not exist emit NOT-CHECKED - never a pass, never a
    block.

Platform adaptation (same precedent as command-center/p2-wave/_measure_one_delivered.py
shard11 repair 2026-10-24): a leading bare `python3` token cannot be spawned by
cmd.exe on this Windows host, so the resolver rewrites the interpreter token to
the live interpreter before spawning, and records BOTH the declared and the
executed command. Nothing else in the declared command is touched.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

THRESHOLDS_NAME = ".coverage-thresholds.json"


def declared_command(project: Path) -> tuple[str | None, dict | None]:
    """Return (command, thresholds) read ONLY from the project root file."""
    path = project / THRESHOLDS_NAME
    if not path.is_file():
        return None, None
    doc = json.loads(path.read_text(encoding="utf-8"))
    cmd = ((doc.get("enforcement") or {}).get("command")) or None
    return cmd, doc.get("thresholds")


def executable_command(declared: str) -> str:
    """Windows adaptation: bare `python3` is not spawnable from cmd.exe."""
    parts = declared.split(" ")
    if parts and parts[0] == "python3":
        parts[0] = sys.executable.replace("\\", "/")
        return " ".join(parts)
    return declared


def resolve_project(project: Path, run: bool = True) -> dict:
    project = Path(project)
    cmd, thresholds = declared_command(project)
    row: dict = {
        "project": project.as_posix(),
        "file_exists": cmd is not None or (project / THRESHOLDS_NAME).is_file(),
        "declared_command": cmd,
        "thresholds": thresholds,
    }
    if cmd is None:
        row.update(
            {
                "result": "NOT-CHECKED",
                "enforcement_ran": False,
                "exit_code": None,
                "blocked": False,
                "pass": False,
                "reason": (
                    "no .coverage-thresholds.json in this project root; "
                    "absence is NOT-CHECKED, never a pass and never a block"
                ),
            }
        )
        return row
    row["file_path"] = (project / THRESHOLDS_NAME).as_posix()
    if not run:
        row.update({"result": "RESOLVED", "enforcement_ran": False, "exit_code": None,
                    "blocked": False, "pass": False,
                    "reason": "declared command resolved but not run (run=False)"})
        return row
    executed = executable_command(cmd)
    proc = subprocess.run(
        executed, cwd=str(project), shell=True,
        capture_output=True, text=True, timeout=300,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    row.update(
        {
            "result": "COMMAND-RAN",
            "executed_command": executed,
            "enforcement_ran": True,
            "exit_code": proc.returncode,
            "stdout_tail": ((proc.stdout or "") + (proc.stderr or "")).strip()[-300:],
            "blocked": False,
            "pass": False,
            "reason": (
                "declared enforcement command executed in this project root; "
                "exit code reported and not interpreted as a coverage pass"
            ),
        }
    )
    return row
