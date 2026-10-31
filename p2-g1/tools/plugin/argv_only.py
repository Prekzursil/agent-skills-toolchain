"""Argv-array-only process invocation. No command-string concatenation."""
from __future__ import annotations

import json
import subprocess
import sys
from typing import Any, Sequence

ENTRYPOINTS = ("spawn", "echo_argv", "wrap_argv_for_shell")


def spawn(argv: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess:
    if isinstance(argv, str):
        raise TypeError("command string is forbidden; pass an argv list")
    kwargs = dict(kwargs)
    kwargs["shell"] = False
    return subprocess.run(list(argv), **kwargs)


def echo_argv(token: str) -> list[str]:
    child = __import__("pathlib").Path(__file__).resolve().parents[1] / "glob-argv-guard" / "fixtures" / "echo_argv.py"
    proc = spawn(
        [sys.executable, "-B", str(child), token],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)
    return parse_echo(proc.stdout)


def parse_echo(stdout: str | None) -> list[str]:
    text = (stdout or "").strip()
    if not text:
        return []
    last = text.splitlines()[-1]
    doc = json.loads(last)
    argv = doc.get("argv")
    return list(argv) if isinstance(argv, list) else []


def wrap_argv_for_shell(shell: str, argv: Sequence[str]) -> list[str]:
    """Wrap an argv list so bash -c never interpolates user tokens."""
    import shlex

    payload = " ".join(shlex.quote(str(x)) for x in argv)
    if shell in {"bash", "sh", "zsh", "git-bash"}:
        return [shell, "-c", 'exec "$0" "$@"', *argv]
    return [shell, *argv]
