"""Parameter pipeline: every sink receives the parameter as bytes, never via a shell.

A workflow parameter travels to a child process through one of four channels --
an argv element, an environment value, a file, or stdin. None of them is ever
interpolated into a shell script string and ``subprocess`` is never asked for
``shell=True``, so ``$(...)``, backticks and ``%VAR%`` arrive byte-identical.

The deliberate shell-splice controls (``unsafe_splice_eval``,
``cmd_percent_expand``) live in :mod:`tools.shell.splice_control` and are only
re-exported here so a static scan of *this* file finds no shell-enabling
construct while probes still import everything from one place.
"""
from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .splice_control import cmd_percent_expand, unsafe_splice_eval

SINKS = (
    "python-argv",
    "printf-argv",
    "env-value",
    "file-bytes",
    "stdin-bytes",
)

_SHELL_BINARIES = {
    "bash",
    "sh",
    "dash",
    "zsh",
    "ksh",
    "cmd",
    "cmd.exe",
    "powershell",
    "powershell.exe",
    "pwsh",
    "pwsh.exe",
}
_SHELL_SCRIPT_FLAGS = {"-c", "/c", "/k", "-command", "-encodedcommand", "-enc", "-e"}
_TEXT_NEEDLES = ("shell=True", "os.system(", "os.popen(", "bash -c", "sh -c", "cmd /c")


@dataclass
class SinkRow:
    sink: str
    received: str
    literal: bool
    canary_present: bool = False


def tools_ok() -> dict[str, bool]:
    return {
        "bash_exists": shutil.which("bash") is not None,
        "printf_exists": shutil.which("printf") is not None,
        "cat_exists": shutil.which("cat") is not None,
        "env_exists": shutil.which("env") is not None,
    }


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _argv_head(node: ast.Call) -> list[str]:
    if not node.args:
        return []
    first = node.args[0]
    if not isinstance(first, (ast.List, ast.Tuple)):
        return []
    out: list[str] = []
    for elt in first.elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            out.append(elt.value)
        else:
            break
    return out


def _call_enables_shell(node: ast.Call) -> bool:
    for kw in node.keywords:
        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            return True
    name = _call_name(node)
    if name in {"system", "popen", "popen2", "popen3", "popen4", "spawnlp", "eval", "exec"}:
        return True
    if name in {"run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput"}:
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            # A single command string is only meaningful to a shell.
            return " " in node.args[0].value.strip()
        head = _argv_head(node)
        if head:
            binary = os.path.basename(head[0]).lower()
            if binary in _SHELL_BINARIES and any(a.lower() in _SHELL_SCRIPT_FLAGS for a in head[1:]):
                return True
    return False


def source_enables_shell(src: str | Path) -> bool:
    """True when ``src`` (source text or a path to it) hands a parameter to a shell.

    Detects ``shell=True``, ``os.system``/``os.popen``, ``eval``/``exec`` and
    argv vectors that start a shell with a script flag (``bash -c``,
    ``cmd /c``, ``pwsh -Command``). Falls back to text needles when the source
    is not parseable Python.
    """
    if isinstance(src, Path) or (isinstance(src, str) and "\n" not in src and os.path.isfile(src)):
        text = Path(src).read_text(encoding="utf-8", errors="replace")
    else:
        text = str(src)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return any(n in text for n in _TEXT_NEEDLES)
    return any(isinstance(n, ast.Call) and _call_enables_shell(n) for n in ast.walk(tree))


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8", errors="surrogateescape")


def _row(sink: str, payload: str, raw: bytes, canary: Path | None) -> SinkRow:
    got = _decode(raw)
    return SinkRow(sink, got, got == payload, canary.is_file() if canary else False)


def _python() -> str:
    return sys.executable or os.environ.get("PYTHON", "python3")


def run_pipeline(payload: str, workdir: Path, canary: Path | None = None) -> list[SinkRow]:
    """Deliver ``payload`` to every sink and record exactly what each one received."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    rows: list[SinkRow] = []
    raw_payload = payload.encode("utf-8", errors="surrogateescape")
    common = {"capture_output": True, "timeout": 20, "cwd": str(workdir)}

    recv_argv = workdir / "recv_argv.py"
    recv_argv.write_bytes(
        b"import os, sys\n"
        b"sys.stdout.buffer.write(os.fsencode(sys.argv[1]) if len(sys.argv) > 1 else b'')\n"
    )
    r = subprocess.run([_python(), "-S", "-B", str(recv_argv), payload], **common)
    rows.append(_row("python-argv", payload, r.stdout, canary))

    r = subprocess.run(["printf", "%s", payload], **common)
    rows.append(_row("printf-argv", payload, r.stdout, canary))

    recv_env = workdir / "recv_env.py"
    recv_env.write_bytes(
        b"import os, sys\n"
        b"sys.stdout.buffer.write(os.environb.get(b'TST0193_PARAM', b''))\n"
    )
    env = dict(os.environ)
    env["TST0193_PARAM"] = payload
    r = subprocess.run([_python(), "-S", "-B", str(recv_env)], env=env, **common)
    rows.append(_row("env-value", payload, r.stdout, canary))

    blob = workdir / "payload.bin"
    blob.write_bytes(raw_payload)
    r = subprocess.run(["cat", str(blob)], **common)
    rows.append(_row("file-bytes", payload, r.stdout, canary))

    r = subprocess.run(["cat"], input=raw_payload, **common)
    rows.append(_row("stdin-bytes", payload, r.stdout, canary))

    return rows


__all__ = [
    "SINKS",
    "SinkRow",
    "cmd_percent_expand",
    "run_pipeline",
    "source_enables_shell",
    "tools_ok",
    "unsafe_splice_eval",
]
