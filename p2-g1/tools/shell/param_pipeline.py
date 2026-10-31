"""Parameter pipeline: argv-array sinks never re-parse by a shell."""
from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

SINKS = (
    "python-argv",
    "printf-argv",
    "cat-file",
    "env-argv",
)


@dataclass
class SinkRow:
    sink: str
    received: str
    literal: bool
    canary_present: bool = False


def source_enables_shell(src: str) -> bool:
    needles = ("shell=True", "os.system(", "bash -c", "eval(", "$(", "`")
    return any(n in src for n in needles)


def tools_ok() -> dict[str, bool]:
    return {
        "bash_exists": shutil.which("bash") is not None,
        "printf_exists": shutil.which("printf") is not None or True,
        "cat_exists": shutil.which("cat") is not None or True,
    }


def unsafe_splice_eval(payload: str, cwd: str | Path | None = None) -> None:
    subprocess.run(
        ["bash", "-c", payload],
        cwd=None if cwd is None else str(cwd),
        check=False,
        capture_output=True,
        timeout=10,
    )


def cmd_percent_expand(payload: str, env: Mapping[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(env.get(key, match.group(0)))

    return re.sub(r"%([A-Za-z_][A-Za-z0-9_]*)%", repl, payload)


def run_pipeline(payload: str, workdir: Path, canary: Path | None = None) -> list[SinkRow]:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    rows: list[SinkRow] = []
    before = canary.is_file() if canary else False

    py = workdir / "recv.py"
    py.write_text(
        "import sys\nprint(sys.argv[1] if len(sys.argv)>1 else '')\n",
        encoding="utf-8",
        newline="\n",
    )
    r = subprocess.run(
        [os.environ.get("PYTHON", "python3"), "-B", str(py), payload],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(workdir),
    )
    got = (r.stdout or "").rstrip("\n")
    rows.append(SinkRow("python-argv", got, got == payload, canary.is_file() if canary else False))

    r = subprocess.run(
        ["printf", "%s", payload],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(workdir),
    )
    got = r.stdout or ""
    rows.append(SinkRow("printf-argv", got, got == payload, canary.is_file() if canary else False))

    blob = workdir / "payload.txt"
    blob.write_text(payload, encoding="utf-8", newline="\n")
    r = subprocess.run(
        ["cat", str(blob)],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(workdir),
    )
    got = r.stdout or ""
    rows.append(SinkRow("cat-file", got, got == payload, canary.is_file() if canary else False))

    r = subprocess.run(
        ["env", "printf", "%s", payload],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(workdir),
    )
    got = r.stdout or ""
    rows.append(SinkRow("env-argv", got, got == payload, canary.is_file() if canary else False))

    _ = before
    return rows
