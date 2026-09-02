"""Run a documented command literally, or refuse to invent substitutions."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

AMBIGUOUS = re.compile(
    r"<[A-Za-z][A-Za-z0-9_-]*>"
    r"|\{[A-Za-z][A-Za-z0-9_]*\}"
    r"|\bYOUR_[A-Z0-9_]+\b"
    r"|\bTBD\b"
    r"|\bTODO\b"
)
WRONG_ARCHIVE = re.compile(r"(?<![\w`'\"])git\s+(?:-C\s+\S+\s+)?archive\b")
PACKAGING = re.compile(r"--format=tar|--output=|\.tar\.gz|-o\s+\S+\.tar")
NEGATED = re.compile(
    r"\b(not|never|no|avoid|unlike|rather than|instead of)\s+[`'\"]?git\s+archive",
    re.I,
)
DESTRUCTIVE = re.compile(
    r"\b(mkfs|diskpart|format\s+[A-Z]:|rm\s+-rf\s+/|curl\s+[^\n|]*\|\s*(ba)?sh)\b",
    re.I,
)


def is_wrong_recipe(command: str) -> bool:
    if not WRONG_ARCHIVE.search(command):
        return False
    if PACKAGING.search(command):
        return False
    if NEGATED.search(command):
        return False
    return True


def is_ambiguous(command: str) -> bool:
    return bool(AMBIGUOUS.search(command))


def run_literal(command: str, cwd: Path, timeout: int = 20) -> dict[str, Any]:
    if is_ambiguous(command):
        return {
            "exit_code": None,
            "status": "not-executed-ambiguous",
            "improvised": False,
            "classification": "ambiguous-step",
            "deviation": (
                "ambiguous-step: placeholders remain; two operators would "
                "substitute different values; command not invented"
            ),
            "stdout": "",
            "stderr": "",
        }
    if DESTRUCTIVE.search(command):
        return {
            "exit_code": None,
            "status": "not-executed-blocked",
            "improvised": False,
            "classification": "blocked-external",
            "deviation": (
                "blocked-external: destructive command not executed in the "
                "confirmation sandbox; recorded rather than improvised"
            ),
            "stdout": "",
            "stderr": "",
        }
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "exit_code": 124,
            "status": "timeout",
            "improvised": False,
            "classification": "documentation-defect",
            "deviation": "command exceeded 20s timeout when run literally",
            "stdout": "",
            "stderr": "TIMEOUT",
        }
    stdout = (proc.stdout or "")[-800:]
    stderr = (proc.stderr or "")[-800:]
    classification = "ok" if proc.returncode == 0 else "documentation-defect"
    deviation = ""
    if proc.returncode != 0:
        deviation = (
            f"literal run exited {proc.returncode}; operator following the "
            "guide as written cannot complete this step"
        )
    result: dict[str, Any] = {
        "exit_code": int(proc.returncode),
        "status": "executed",
        "improvised": False,
        "classification": classification,
        "stdout": stdout,
        "stderr": stderr,
    }
    if deviation:
        result["deviation"] = deviation
    if is_wrong_recipe(command):
        result["classification"] = "wrong-recipe"
        extra = (
            "guide prescribes git archive to read blob bytes; on this platform "
            "that recipe is the measured CRLF trap. corrected recipe: "
            "git cat-file -p <rev>:<path>"
        )
        result["deviation"] = (
            (deviation + "; " if deviation else "") + extra
        )
        result["corrected_recipe"] = "git cat-file -p <rev>:<path>"
    return result
