"""Argv builder used by IMP-0161: prompt routed to --prompt-file."""
from __future__ import annotations

from typing import Sequence


def build(
    binary: str,
    prompt_file: str | None = None,
    timeout_seconds: int | None = None,
    prompt: str | None = None,
) -> list[str]:
    argv = [str(binary)]
    if timeout_seconds is not None:
        argv.extend(["--timeout", str(timeout_seconds)])
    if prompt_file:
        argv.extend(["--prompt-file", str(prompt_file)])
    if prompt:
        raise ValueError("prompt body must not be placed on argv")
    return argv
