#!/usr/bin/env python3
"""Execute generated local experiments and score discrimination."""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PRESENT_CONTROL = "command-center/WORK-UNIT-CATALOG.json"
ABSENT_CONTROL = "command-center/research/evidence-quality/__no-such-RES-0153__.json"
RUN = "RUN"
UNRUN = "GENERATED-UNRUN"
NEEDS = "NEEDS-HUMAN-FRAMING"


def sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _exists(rel: str) -> str:
    p = Path(rel).expanduser()
    if not p.is_absolute():
        p = REPO / p
    return "exists" if p.is_file() else "absent"


def _run_cmd(command: str, timeout: int = 20) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        command,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, out


def execute(generated: dict) -> dict:
    """Run a generator record. URL-shaped rows stay GENERATED-UNRUN."""
    status = generated.get("status")
    if status == NEEDS:
        return {
            "run_status": NEEDS,
            "observed": None,
            "matched_expectation": None,
            "discriminating": False,
            "present_control": None,
            "absent_control": None,
            "exit_code": None,
            "output": None,
        }

    if generated.get("kind") == "url-shape" or not generated.get("runnable_locally"):
        return {
            "run_status": UNRUN,
            "observed": None,
            "matched_expectation": None,
            "discriminating": False,
            "present_control": None,
            "absent_control": None,
            "exit_code": None,
            "output": "not-run: requires network or non-local observable",
        }

    code, output = _run_cmd(str(generated["command"]))
    observed = (output.splitlines()[-1] if output else "").strip()
    expect = str(generated.get("expected_observation") or "")
    matched = observed == expect and code == 0
    present = _exists(PRESENT_CONTROL)
    absent = _exists(ABSENT_CONTROL)
    both_states = present == "exists" and absent == "absent"
    discriminating = bool(matched and both_states)
    if generated.get("kind") == "path-exists":
        discriminating = bool(matched and both_states)
    return {
        "run_status": RUN,
        "observed": observed,
        "matched_expectation": matched,
        "discriminating": discriminating,
        "present_control": present,
        "absent_control": absent,
        "exit_code": code,
        "output": output[-500:],
    }


def combine(row: dict, generated: dict, executed: dict) -> dict:
    merged = dict(row)
    merged["experiment"] = generated
    merged["execution"] = executed
    if generated.get("status") == NEEDS:
        merged["final_status"] = NEEDS
    else:
        merged["final_status"] = executed["run_status"]
    return merged
