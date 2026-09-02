#!/usr/bin/env python3
"""Run recorded repro steps verbatim. No improvisation on the first attempt."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
N_RUNS = 3
TIMEOUT = 20
REQUIRES_PREFIX = "# REQUIRES:"


def run_verbatim(command: str) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("CNF0016_TRIGGER", None)
    try:
        proc = subprocess.run(
            command,
            cwd=str(REPO),
            shell=True,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=env,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return {"exit_code": proc.returncode, "output": out, "timeout": False}
    except subprocess.TimeoutExpired:
        return {"exit_code": 124, "output": f"TIMEOUT after {TIMEOUT}s: {command}", "timeout": True}


def scripts_in_commands(commands: list[str]) -> list[Path]:
    found: list[Path] = []
    for cmd in commands:
        for tok in cmd.split():
            tok = tok.strip("'\"")
            if tok.endswith(".py"):
                p = REPO / tok
                if p.is_file() and p not in found:
                    found.append(p)
    return found


def requires_header(path: Path) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[:30]
    except OSError:
        return None
    for line in lines:
        if line.startswith(REQUIRES_PREFIX):
            return line[len(REQUIRES_PREFIX) :].strip()
    return None


def named_missing_step(commands: list[str], expected: str, observed: str) -> str:
    if not commands:
        return "no recorded repro steps"
    for script in scripts_in_commands(commands):
        req = requires_header(script)
        if req:
            return req
    tail = (observed or "").replace("\n", " ").strip()[:240]
    return (
        "verbatim commands did not produce expected failure "
        f"{expected!r}; observed={tail!r}"
    )


def measure_brief(brief: dict, runs: int = N_RUNS) -> dict:
    ident = brief["id"]
    commands = list(brief.get("repro_steps") or [])
    expected = str(brief.get("expected_failure") or "")
    observations: list[dict] = []
    matched = 0
    last_out = "NOT-RUN: no recorded repro steps"
    if not commands:
        missing = named_missing_step(commands, expected, last_out)
        return {
            "id": ident,
            "severity": brief.get("severity") or "P0",
            "title": brief.get("title") or "",
            "verdict": "INSUFFICIENT",
            "commands": [],
            "observed_output": last_out,
            "missing_step": missing,
            "run_score": f"0/{runs}",
            "verbatim": True,
            "improvised": False,
            "runs": [
                {
                    "n": i,
                    "exit_code": None,
                    "matched": False,
                    "output_tail": last_out,
                }
                for i in range(1, runs + 1)
            ],
        }

    for i in range(1, runs + 1):
        # Floor: concatenate recorded steps in order, each run fully verbatim.
        chunks: list[str] = []
        code = 0
        for cmd in commands:
            one = run_verbatim(cmd)
            chunks.append(one["output"])
            code = int(one["exit_code"])
        output = "".join(chunks)
        hit = bool(expected) and expected in output
        if hit:
            matched += 1
        last_out = output
        observations.append(
            {
                "n": i,
                "exit_code": code,
                "matched": hit,
                "output_tail": output[-800:],
            }
        )

    score = f"{matched}/{runs}"
    if matched == runs:
        verdict = "PASS"
        missing: str | None = None
    else:
        verdict = "INSUFFICIENT"
        missing = named_missing_step(commands, expected, last_out)
        if 0 < matched < runs:
            missing = f"flaky reproduction: matched {score}; not a PASS. {missing}"

    return {
        "id": ident,
        "severity": brief.get("severity") or "P0",
        "title": brief.get("title") or "",
        "verdict": verdict,
        "commands": commands,
        "observed_output": last_out[-4000:] if last_out else "EMPTY-OUTPUT",
        "missing_step": missing,
        "run_score": score,
        "verbatim": True,
        "improvised": False,
        "runs": observations,
    }


def measure_all(briefs: list[dict] | None = None) -> list[dict]:
    from corpus import p0_records, strip_brief

    if briefs is None:
        briefs = [strip_brief(d) for d in p0_records()]
    return [measure_brief(b) for b in briefs]
