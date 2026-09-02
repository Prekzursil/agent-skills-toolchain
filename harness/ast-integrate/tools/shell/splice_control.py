"""Detector controls for the parameter pipeline (TST-0193).

These deliberately DO what the pipeline must never do: hand a parameter to a shell
parser (``bash -c``) or a ``%VAR%`` expander. A probe uses them to prove it can
observe substitution (the canary file appears) before asserting the real sinks in
``param_pipeline`` keep the same payload literal. They live in their own module so a
static scan of the pipeline source finds no shell-enabling construct.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Mapping


def unsafe_splice_eval(payload: str, cwd: str | Path | None = None) -> None:
    """Splice ``payload`` into a shell parser. CONTROL ONLY: substitution WILL run."""
    subprocess.run(
        ["bash", "-c", payload],
        cwd=None if cwd is None else str(cwd),
        check=False,
        capture_output=True,
        timeout=10,
    )


def cmd_percent_expand(payload: str, env: Mapping[str, str]) -> str:
    """Emulate cmd.exe ``%VAR%`` expansion. CONTROL ONLY: shows the value can change."""

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(env.get(key, match.group(0)))

    return re.sub(r"%([A-Za-z_][A-Za-z0-9_]*)%", repl, payload)


__all__ = ["cmd_percent_expand", "unsafe_splice_eval"]
